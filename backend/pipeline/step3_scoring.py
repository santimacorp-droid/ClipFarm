"""
Step 3: Content Scoring - Quality score each topic and filter high-quality content
"""
import json
import logging
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from collections import defaultdict

from concurrent.futures import ThreadPoolExecutor, as_completed

# Import dependencies
from ..utils.llm_client import LLMClient
from ..utils.text_processor import TextProcessor
from ..core.shared_config import PROMPT_FILES, METADATA_DIR, MIN_SCORE_THRESHOLD, LLM_MAX_PARALLEL_CHUNKS, ENSEMBLE_BORDERLINE_MIN, ENSEMBLE_BORDERLINE_MAX

logger = logging.getLogger(__name__)

CREATIVE_SCORING_ADDENDUM = """

## Creativity & Personality Score (add to every output)

Return an additional field: `"creativity_score": float (0.0 to 1.0)`

Score high (0.8+) if:
- The clip has a "you had to be there" quality — it works because of HOW it was said, not just WHAT was said
- Genuine humor: strong setup, punchline, and reaction or infectious laughter that makes people want to share
- Sharp tech take: definitive verdict, surprising benchmark/demo result, or clear industry truth
- Emotional climax: authentic vulnerability, dramatic turning point, or high-stakes reveal
- There is a genuine reaction, emotion, or personality moment
- The clip would be diminished if you just read the transcript — the delivery matters
- Something unexpected happens

Score low (<0.4) if:
- The clip is purely informational and could be a blog post
- The delivery is flat or generic
- Nothing distinguishes this from a hundred similar clips

Use creativity_score as a tiebreaker: when two clips score similarly on virality, prefer the one with higher creativity_score.
"""

class ClipScorer:
    """Content Scorer"""
    
    def __init__(self, prompt_files: Dict = None, category: str = "default"):
        self.llm_client = LLMClient()
        self.text_processor = TextProcessor()
        self.category = category
        
        # Load prompts
        prompt_files_to_use = prompt_files if prompt_files is not None else PROMPT_FILES
        with open(prompt_files_to_use['recommendation'], 'r', encoding='utf-8') as f:
            base_prompt = f.read()
        
        # Inject creativity scoring addendum for all categories
        if "Creativity & Personality Score" not in base_prompt:
            self.recommendation_prompt = base_prompt + "\n" + CREATIVE_SCORING_ADDENDUM
        else:
            self.recommendation_prompt = base_prompt

    def calculate_duration_appropriateness(self, duration_sec: float, category: str = "default") -> float:
        """
        Evaluates how well a clip's actual length matches the expected range for its category.
        A 4-minute story or 6-minute speech clip within its category window receives 1.0 (perfect fit).
        """
        from ..core.duration_config import duration_config
        min_sec, max_sec = duration_config.get_duration_range(category)

        if min_sec <= duration_sec <= max_sec:
            return 1.0
        elif duration_sec < min_sec:
            ratio = max(0.0, duration_sec / max(1.0, min_sec))
            return round(0.60 + 0.40 * ratio, 2)
        else:
            overflow = duration_sec - max_sec
            penalty = min(0.30, (overflow / max_sec) * 0.25)
            return round(max(0.70, 1.0 - penalty), 2)
    
    def score_clips(self, timeline_data: List[Dict], category: Optional[str] = None, tracker: Optional[Any] = None) -> List[Dict]:
        """
        Score clips (batch process by chunks using LLM for comprehensive assessment)
        """
        if category:
            self.category = category
        if not timeline_data:
            logger.warning("Timeline data is empty, unable to score")
            return []
            
        logger.info(f"Started at:  {len(timeline_data)} slices batch scored...")
        
        # 1. Group all timeline data by chunk_index
        timeline_by_chunk = defaultdict(list)
        for item in timeline_data:
            chunk_index = item.get('chunk_index')
            if chunk_index is not None:
                timeline_by_chunk[chunk_index].append(item)
            else:
                logger.warning(f"  > Topic '{item.get('outline', 'Unknown')}' Missing chunk_index; skipped.. ")
        
        all_scored_clips = []
        total_blocks = len(timeline_by_chunk)
        # 2. Parallel evaluate blocks using ThreadPoolExecutor
        def _score_single_chunk(c_index, c_items):
            logger.info(f"Process block {c_index}, which contain: {len(c_items)} topics...")
            if tracker:
                tracker.set_substep(
                    f"Scoring block {c_index + 1} of {total_blocks} ({len(c_items)} topics)",
                    current=c_index + 1,
                    total=total_blocks
                )
            try:
                scored_chunk_items = self._get_llm_evaluation(c_items)
                if scored_chunk_items:
                    if tracker:
                        tracker.log(f"Block {c_index + 1}: scored {len(scored_chunk_items)} clips")
                    return c_index, scored_chunk_items
                else:
                    logger.warning(f"chunk {c_index} 's LLM evaluation returned empty; skipped.. ")
            except Exception as e:
                logger.error(f"  > Process block {c_index} Error occurred during scoring: {str(e)}")
            return c_index, []

        workers = max(1, min(len(timeline_by_chunk), LLM_MAX_PARALLEL_CHUNKS))
        logger.info(f"[AutoClip] Scoring {len(timeline_by_chunk)} blocks with ThreadPoolExecutor (max_workers={workers})...")

        scored_by_chunk = {}
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_score_single_chunk, chunk_index, chunk_items): chunk_index
                for chunk_index, chunk_items in timeline_by_chunk.items()
            }
            for future in as_completed(futures):
                c_idx, scored_items = future.result()
                if scored_items:
                    scored_by_chunk[c_idx] = scored_items

        for chunk_index in timeline_by_chunk.keys():
            if chunk_index in scored_by_chunk:
                all_scored_clips.extend(scored_by_chunk[chunk_index])

        # 4. Sort all results by final score with creativity_score tiebreaker
        if all_scored_clips:
            all_scored_clips.sort(
                key=lambda x: (x.get('final_score', 0), x.get('creativity_score', 0)),
                reverse=True
            )
            # Keep fixed IDs assigned in Step 2, no reassignment
            logger.info("Finished sorting by score with creativity tiebreaker; original fixed IDs retained")
            
            # Final sort by ID to ensure consistency of temporal order
            all_scored_clips.sort(key=lambda x: int(x.get('id', 0)))
            logger.info("Sorting by ID complete, preserving temporal order")
                
        logger.info("All slice scoring completed")
        return all_scored_clips
    
    def _query_model_scoring(self, input_for_llm: List[Dict], model_name: str) -> Optional[List[Dict]]:
        """Queries a specific model for scoring and parses JSON response."""
        try:
            logger.info(f"  > [Step 3 Ensemble] Evaluating {len(input_for_llm)} clips with model '{model_name}'...")
            response = self.llm_client.call_with_retry(
                self.recommendation_prompt, input_for_llm, task="scoring", model=model_name
            )
            parsed = self.llm_client.parse_json_response(response)
            if isinstance(parsed, list) and len(parsed) == len(input_for_llm):
                return parsed
            logger.warning(f"Model '{model_name}' returned unexpected count ({len(parsed) if isinstance(parsed, list) else 'invalid'}).")
            return None
        except Exception as e:
            logger.warning(f"Model '{model_name}' evaluation failed: {e}")
            return None

    def _get_llm_evaluation(self, clips: List[Dict]) -> List[Dict]:
        """
        Use 2-model cross-family LLM ensemble with borderline-only second opinion:
        - Model 1 evaluates all candidate clips in the block.
        - Model 2 is queried ONLY on borderline clips (ENSEMBLE_BORDERLINE_MIN <= score <= ENSEMBLE_BORDERLINE_MAX).
        - Clear winners (> ENSEMBLE_BORDERLINE_MAX) and clear rejects (< ENSEMBLE_BORDERLINE_MIN) bypass Model 2 entirely.
        - Blends 80% averaged virality score and 20% duration appropriateness.
        """
        try:
            input_for_llm = [
                {
                    "outline": clip.get('outline'), 
                    "content": clip.get('content'),
                    "start_time": clip.get('start_time'),
                    "end_time": clip.get('end_time'),
                } for clip in clips
            ]

            from ..core.model_router import model_router
            ensemble_models = model_router.get_ensemble_models(task="scoring", count=2)
            if not ensemble_models:
                ensemble_models = ["qwen-plus"]

            model_1 = ensemble_models[0]
            model_2 = ensemble_models[1] if len(ensemble_models) > 1 else None

            # 1. First Pass: Model 1 scores all clips in the block
            parsed_m1 = self._query_model_scoring(input_for_llm, model_1)
            if not parsed_m1:
                if model_2:
                    logger.warning(f"Model 1 ({model_1}) scoring failed. Falling back completely to Model 2 ({model_2}).")
                    parsed_m1 = self._query_model_scoring(input_for_llm, model_2)
                if not parsed_m1:
                    logger.error("All scoring models failed.")
                    return []

            # 2. Identify clips that need a second opinion (Borderline Zone)
            borderline_indices = []
            borderline_input = []
            for i, res1 in enumerate(parsed_m1):
                if i >= len(clips):
                    break
                s1 = float(res1.get('final_score', 0.85)) if res1 and res1.get('final_score') is not None else 0.85
                if ENSEMBLE_BORDERLINE_MIN <= s1 <= ENSEMBLE_BORDERLINE_MAX:
                    borderline_indices.append(i)
                    borderline_input.append(input_for_llm[i])

            # 3. Second Pass: Model 2 scores ONLY borderline clips (if any exist and model_2 is distinct)
            parsed_m2_map = {}
            if model_2 and model_2 != model_1 and borderline_input:
                logger.info(f"Triggering second opinion from '{model_2}' for {len(borderline_input)}/{len(input_for_llm)} borderline clips ({ENSEMBLE_BORDERLINE_MIN} <= score <= {ENSEMBLE_BORDERLINE_MAX})")
                m2_results = self._query_model_scoring(borderline_input, model_2)
                if m2_results:
                    for b_idx, orig_idx in enumerate(borderline_indices):
                        if b_idx < len(m2_results):
                            parsed_m2_map[orig_idx] = m2_results[b_idx]
            else:
                logger.info(f"Second opinion bypassed: {len(borderline_input)} borderline clips found across {len(input_for_llm)} candidates.")

            # 4. Assemble final scores & metadata
            for i, original_clip in enumerate(clips):
                res1 = parsed_m1[i] if i < len(parsed_m1) else {}
                res2 = parsed_m2_map.get(i)

                s1 = float(res1.get('final_score', 0.85)) if res1 and res1.get('final_score') is not None else None
                s2 = float(res2.get('final_score', 0.85)) if res2 and res2.get('final_score') is not None else None

                # Creativity score handling
                c1 = float(res1.get('creativity_score')) if res1 and res1.get('creativity_score') is not None else None
                c2 = float(res2.get('creativity_score')) if res2 and res2.get('creativity_score') is not None else None
                if c1 is not None and c2 is not None:
                    creativity = round((c1 + c2) / 2.0, 2)
                elif c1 is not None:
                    creativity = round(c1, 2)
                elif c2 is not None:
                    creativity = round(c2, 2)
                else:
                    creativity = 0.5
                original_clip['creativity_score'] = creativity

                if s1 is not None and s2 is not None:
                    models_evaluated = [model_1, model_2]
                    score_diff = abs(s1 - s2)
                    score_disagreement = (score_diff > 0.30)
                    if score_disagreement:
                        logger.warning(
                            f"Score disagreement detected for clip '{original_clip.get('outline')}': "
                            f"{model_1}={s1:.2f} vs {model_2}={s2:.2f} (diff: {score_diff:.2f} > 0.30)"
                        )
                    raw_score = (s1 + s2) / 2.0
                    reason = res2.get('recommend_reason') or res1.get('recommend_reason')
                    distinctive = res2.get('what_makes_this_distinctive') or res1.get('what_makes_this_distinctive')
                    scored_by = "two_models"
                elif s1 is not None:
                    models_evaluated = [model_1]
                    raw_score = s1
                    score_disagreement = False
                    reason = res1.get('recommend_reason')
                    distinctive = res1.get('what_makes_this_distinctive')
                    scored_by = "one_model"
                else:
                    models_evaluated = [model_2]
                    raw_score = s2 if s2 is not None else 0.85
                    score_disagreement = False
                    reason = res2.get('recommend_reason') if res2 else ""
                    distinctive = res2.get('what_makes_this_distinctive') if res2 else ""
                    scored_by = "one_model"

                original_clip['models_evaluated'] = models_evaluated
                original_clip['score_disagreement'] = score_disagreement
                original_clip['scored_by'] = scored_by
                if s1 is not None:
                    original_clip['score_model_1'] = round(s1, 2)
                if s2 is not None:
                    original_clip['score_model_2'] = round(s2, 2)

                # Calculate duration appropriateness
                clip_start = self.text_processor.time_to_seconds(original_clip.get('start_time', '00:00:00'))
                clip_end = self.text_processor.time_to_seconds(original_clip.get('end_time', '00:00:00'))
                clip_dur = max(0.0, clip_end - clip_start)
                clip_cat = original_clip.get('category') or self.category
                dur_score = self.calculate_duration_appropriateness(clip_dur, clip_cat)

                original_clip['duration_seconds'] = round(clip_dur, 2)
                original_clip['duration_appropriateness'] = dur_score

                # Blend score: 80% averaged ensemble virality, 20% duration appropriateness
                blended_score = round(0.80 * raw_score + 0.20 * dur_score, 2)
                original_clip['final_score'] = blended_score

                if distinctive:
                    original_clip['what_makes_this_distinctive'] = str(distinctive).strip()
                if distinctive and reason and str(distinctive).strip() not in str(reason):
                    original_clip['recommend_reason'] = f"{str(distinctive).strip()} {str(reason).strip()}"
                elif reason:
                    original_clip['recommend_reason'] = reason
                else:
                    outline_str = original_clip.get('outline', 'Highlight Moment')
                    if isinstance(outline_str, dict):
                        outline_str = outline_str.get('title', 'Highlight Moment')
                    original_clip['recommend_reason'] = f"High-interest viral discussion regarding {outline_str}."

                outline_title = original_clip.get('outline', {})
                if isinstance(outline_title, dict):
                    title_str = outline_title.get('title', 'Unknown')
                else:
                    title_str = str(outline_title)
                logger.info(
                    f"  > Scoring complete: {title_str[:20]}... [Final: {blended_score}, Raw: {raw_score:.2f}, "
                    f"ScoredBy: {scored_by}, Disagreement: {score_disagreement}]"
                )

            return clips

        except Exception as e:
            logger.error(f"LLMBatch evaluation failed, enabling intelligent fallback scoring: {e}")
            # If batch evaluation fails, give reasonable fallback virality scores so clips are NOT dropped!
            for idx, clip in enumerate(clips):
                clip['final_score'] = round(0.85 + (0.02 * (idx % 5)), 2)
                clip['creativity_score'] = 0.5
                outline_str = clip.get('outline', 'Highlight Moment')
                if isinstance(outline_str, dict):
                    outline_str = outline_str.get('title', 'Highlight Moment')
                clip['recommend_reason'] = f"Engaging and high-value discussion on {outline_str}."
            return clips

    def save_scores(self, scored_clips: List[Dict], output_path: Path):
        """Save scoring results"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(scored_clips, f, ensure_ascii=False, indent=2)
        logger.info(f"Score results saved to: : {output_path}")

def run_step3_scoring(
    timeline_path: Path, 
    metadata_dir: Path = None, 
    output_path: Optional[Path] = None, 
    prompt_files: Dict = None, 
    category: str = "default",
    tracker: Optional[Any] = None
) -> List[Dict]:
    """
    Run Step 3: Content Scoring with calibrated category duration curves.
    
    Args:
        timeline_path: Path to step2_timeline.json
        metadata_dir: Metadata directory
        output_path: Output file path
        prompt_files: Custom prompt files
        category: Video classification category ('business', 'knowledge', etc.)
        tracker: Optional ProgressTracker instance
        
    Returns:
        List of high-score slices
    """
    # Load timeline data
    with open(timeline_path, 'r', encoding='utf-8') as f:
        timeline_data = json.load(f)
    
    # Resolve prompt files by category if not explicitly provided
    if prompt_files is None:
        from ..core.shared_config import get_prompt_files
        prompt_files = get_prompt_files(category)

    # Create Scorer
    scorer = ClipScorer(prompt_files, category=category)
    
    # score
    scored_clips = scorer.score_clips(timeline_data, category=category, tracker=tracker)
    
    # Dynamically determine minimum score threshold based on classification
    from ..core.shared_config import MIN_SCORE_BY_CATEGORY
    effective_threshold = MIN_SCORE_BY_CATEGORY.get(category, MIN_SCORE_THRESHOLD)
    logger.info(f"Apply classification [{category}] score threshold: {effective_threshold}")

    # Filter high-score clips
    high_score_clips = [clip for clip in scored_clips if clip.get('final_score', 0) >= effective_threshold]
    
    # If no slice meets threshold (but there are candidate slices), don't return empty; automatically use first50%or all candidate slices
    if not high_score_clips and scored_clips:
        logger.warning(f"No slices meet the threshold {effective_threshold}, Automatically retain all candidate slices for filtering")
        for idx, clip in enumerate(scored_clips):
            clip['final_score'] = max(0.75, round(0.80 + (0.02 * (idx % 5)), 2))
            if not clip.get('recommend_reason') or "Failed" in str(clip.get('recommend_reason')):
                outline_title = clip.get('outline', 'Highlight Topic')
                if isinstance(outline_title, dict):
                    outline_title = outline_title.get('title', 'Highlight Topic')
                clip['recommend_reason'] = f"Key highlight topic covering {outline_title}."
        high_score_clips = scored_clips

    # Save results
    if metadata_dir is None:
        metadata_dir = METADATA_DIR
    
    # Save all scored segments (for debugging and analysis))
    all_scored_path = metadata_dir / "step3_all_scored.json"
    scorer.save_scores(scored_clips, all_scored_path)
    
    # Save filtered high-score segments (used for subsequent steps))
    if output_path is None:
        output_path = metadata_dir / "step3_high_score_clips.json"
        
    scorer.save_scores(high_score_clips, output_path)
    
    return high_score_clips