"""
Step 1: Outline extraction - Extracts structural outline from transcription text
"""
import json
import logging
import re
from typing import List, Dict, Any, Optional
from pathlib import Path

from concurrent.futures import ThreadPoolExecutor, as_completed

# Imports dependencies
from ..utils.llm_client import LLMClient
from ..utils.text_processor import TextProcessor
from ..core.shared_config import PROMPT_FILES, METADATA_DIR, get_prompt_files, LLM_MAX_PARALLEL_CHUNKS
from ..core.duration_config import duration_config

logger = logging.getLogger(__name__)

class OutlineExtractor:
    """Outline Extractor (Refactored)）"""
    
    def __init__(self, metadata_dir: Path = None, prompt_files: Dict = None, category: str = "default"):
        self.llm_client = LLMClient()
        self.text_processor = TextProcessor()
        self.category = category
        
        # Uses the provided metadata_dir or default value
        if metadata_dir is None:
            metadata_dir = METADATA_DIR
        self.metadata_dir = metadata_dir
        
        # Uses the provided prompt_files or category-based prompt files
        if prompt_files is None:
            prompt_files = get_prompt_files(self.category)
        
        # Loads prompts
        outline_file = prompt_files.get('outline', PROMPT_FILES['outline'])
        with open(outline_file, 'r', encoding='utf-8') as f:
            self.outline_prompt = f.read()
            
        # Append category-specific duration guidance to guarantee no 1-minute compression
        duration_guideline = duration_config.get_prompt_instruction(self.category)
        if "IMPORTANT DURATION GUIDELINE" not in self.outline_prompt:
            self.outline_prompt += f"\n\n{duration_guideline}\n"
            
        # Creates directory for storing intermediate text blocks
        self.chunks_dir = self.metadata_dir / "step1_chunks"
        self.chunks_dir.mkdir(parents=True, exist_ok=True)
        # Creates directory for storing intermediate SRT blocks
        self.srt_chunks_dir = self.metadata_dir / "step1_srt_chunks"
        self.srt_chunks_dir.mkdir(parents=True, exist_ok=True)

    def _build_critique_prompt(self, candidate_moments: list, category: str = "default") -> str:
        """
        Builds a high-precision critique prompt for Model B to review Model A's candidate moments.
        Model B's job:
        1. PRUNE: Remove redundant, generic, or incomplete moments.
        2. ADD: Identify up to 3 standout moments genuinely missed by Model A.
        """
        import json
        clean_candidates = []
        for m in candidate_moments:
            clean_candidates.append({
                "id": m.get("id"),
                "title": m.get("title") or m.get("outline"),
                "topic": m.get("topic"),
                "start_anchor": m.get("start_anchor"),
                "end_anchor": m.get("end_anchor"),
                "why_clip_worthy": m.get("why_clip_worthy") or m.get("topic")
            })

        candidates_json = json.dumps(clean_candidates, ensure_ascii=False, indent=2)

        return f"""# Role: Senior Video Editor & Content Strategist (Critique & Refinement)
You are reviewing candidate viral moments extracted from a video transcript for the category: '{category}'.

## Candidate Moments Extracted by First Reviewer:
```json
{candidates_json}
```

## Your Directives (TWO TASKS ONLY):
1. **PRUNE (Quality Gate)**:
   - Keep moments that have strong hooks, coherent thoughts, and high standalone interest.
   - Discard moments that are weak, redundant/overlapping with another better candidate, or cut off mid-thought.
   - For every kept moment, mark `"action": "keep"`.

2. **ADD (Gap Detection - Max 3)**:
   - Identify up to 3 exceptional, high-voltage moments in the transcript text that the first reviewer MISSED:
     * Genuinely hilarious exchanges or banter (setup + punchline + reaction)
     * Sharp tech takes, surprising benchmarks, or definitive product verdicts
     * Deep storytelling turning points or emotional revelations
   - Do NOT add filler or generic conversation. Only add if it meets the viral bar for '{category}'.
   - For every new moment, mark `"action": "add"`.

## Output Format:
Return ONLY a valid JSON array of the final curated moments:
```json
[
  {{
    "title": "Punchy Title (Max 8 words)",
    "topic": "Concise topic summary",
    "action": "keep",
    "confidence": "validated",
    "start_anchor": "Exact opening words",
    "end_anchor": "Exact closing words",
    "why_clip_worthy": "Why this specific moment hooks viewers"
  }},
  {{
    "title": "Newly Discovered Standout Moment",
    "topic": "Concise topic summary",
    "action": "add",
    "confidence": "added",
    "start_anchor": "Exact opening words in transcript",
    "end_anchor": "Exact closing words in transcript",
    "why_clip_worthy": "Why this missed moment is essential"
  }}
]
```
Important:
- Return ONLY the JSON array. Do not include markdown preamble or notes."""

    def extract_outline(self, srt_path: Path, tracker: Optional[Any] = None) -> List[Dict]:
        """
        Extracts video outline from an SRT file

        Args:
            srt_path: Path to the SRT file
            tracker: Optional ProgressTracker instance

        Returns:
            List of video outlines
        """
        logger.info("Beginning to extract video outline...")
        
        # 1. Parses SRT file
        try:
            srt_data = self.text_processor.parse_srt(srt_path)
            if not srt_data:
                logger.warning("SRTFile is empty or parsing failed")
                return []
        except Exception as e:
            logger.error(f"Failed to parse SRT file: {e}")
            return []
            
        # 2. Time-based intelligent chunking
        chunks = self.text_processor.chunk_srt_data(srt_data, interval_minutes=30)
        logger.info(f"Text already split by~30minute(s)/Block splitting, total{len(chunks)}block")
        
        # 3. Saves text blocks and SRT blocks to intermediate files
        chunk_files = self._save_chunks_to_files(chunks)
        self._save_srt_chunks(chunks)
        
        all_outlines = []
        
        # 4. Multi-model sequential critique extraction (Model A extract -> Model B critique)
        from ..core.model_router import model_router
        ensemble_models = model_router.get_ensemble_models(task="moment_extraction", count=2)
        if not ensemble_models:
            ensemble_models = ["qwen-plus"]
        model_a = ensemble_models[0]
        model_b = ensemble_models[1] if len(ensemble_models) > 1 else None
        logger.info(f"Step 1 sequential critique active: Extractor={model_a}, Reviewer={model_b}")
        
        def _process_single_chunk(chunk_idx: int, chunk_path: Path) -> tuple:
            logger.info(f"Processing chunk {chunk_idx+1}/{len(chunks)}: {chunk_path.name}")
            substep_label = (
                f"Chunk {chunk_idx + 1} of {len(chunk_files)} · {model_a}->{model_b}"
                if (model_b and model_b != model_a)
                else f"Chunk {chunk_idx + 1} of {len(chunk_files)} · {model_a}"
            )
            if tracker:
                tracker.set_substep(
                    substep_label,
                    current=chunk_idx + 1,
                    total=len(chunk_files)
                )
            chunk_outlines = []
            try:
                with open(chunk_path, 'r', encoding='utf-8') as f:
                    chunk_text = f.read()
                
                input_data = {"text": chunk_text}
                
                # Round 1: Model A extracts candidates
                logger.info(f"  > [Round 1] Querying extractor '{model_a}' for chunk {chunk_idx+1}...")
                response_a = None
                try:
                    response_a = self.llm_client.call_with_retry(
                        self.outline_prompt, input_data, task="moment_extraction", model=model_a
                    )
                except Exception as mod_err:
                    logger.warning(f"  > Extractor '{model_a}' failed on chunk {chunk_idx+1}: {mod_err}")

                parsed_a = self._parse_outline_response(response_a, chunk_idx) if response_a else []
                for p in parsed_a:
                    p['source_model'] = model_a
                    p['confidence'] = "unverified"

                # Round 2: Model B critique or fallback
                if parsed_a and model_b and model_b != model_a:
                    try:
                        logger.info(f"  > [Round 2] Querying reviewer '{model_b}' to critique {len(parsed_a)} moments from chunk {chunk_idx+1}...")
                        critique_prompt = self._build_critique_prompt(parsed_a, category=self.category)
                        response_b = self.llm_client.call_with_retry(
                            critique_prompt, input_data, task="moment_extraction", model=model_b
                        )
                        parsed_critique = None
                        if response_b:
                            try:
                                parsed_critique = self.llm_client.parse_json_response(response_b)
                            except Exception as parse_err:
                                logger.warning(f"  > Failed to parse Model B critique response: {parse_err}")

                        if isinstance(parsed_critique, list) and len(parsed_critique) > 0:
                            curated_moments = []
                            for item in parsed_critique:
                                if not isinstance(item, dict):
                                    continue
                                action = str(item.get("action", "keep")).lower().strip()
                                if action in ("drop", "prune", "discard", "delete", "remove"):
                                    continue

                                title = item.get("title") or item.get("topic")
                                if not title:
                                    continue

                                is_add = (action == "add")
                                confidence = "added" if is_add else "validated"

                                subtopics = []
                                topic_val = item.get("topic")
                                if topic_val and str(topic_val).strip():
                                    subtopics.append(str(topic_val).strip())
                                for k in ["subtopics", "content", "points", "insights"]:
                                    val = item.get(k)
                                    if isinstance(val, list):
                                        subtopics.extend([str(x).strip() for x in val if str(x).strip()])
                                    elif isinstance(val, str) and val.strip() and val.strip() not in subtopics:
                                        subtopics.append(val.strip())

                                # Attempt match with parsed_a candidates to inherit timing / metadata
                                matched_cand = None
                                if not is_add:
                                    t_clean = str(title).strip().lower()
                                    for cand in parsed_a:
                                        c_clean = str(cand.get("title", "")).strip().lower()
                                        if t_clean == c_clean or (len(t_clean) > 6 and (t_clean in c_clean or c_clean in t_clean)):
                                            matched_cand = cand
                                            break

                                moment = {
                                    "title": str(title).strip(),
                                    "subtopics": list(dict.fromkeys(subtopics + (matched_cand.get("subtopics", []) if matched_cand else []))),
                                    "chunk_index": chunk_idx,
                                    "category": item.get("category") or self.category,
                                    "source_model": f"{model_a}+{model_b}" if not is_add else model_b,
                                    "confidence": confidence,
                                    "action": "add" if is_add else "keep",
                                }
                                if item.get("start_anchor"):
                                    moment["start_anchor"] = item["start_anchor"]
                                elif matched_cand and matched_cand.get("start_anchor"):
                                    moment["start_anchor"] = matched_cand["start_anchor"]

                                if item.get("end_anchor"):
                                    moment["end_anchor"] = item["end_anchor"]
                                elif matched_cand and matched_cand.get("end_anchor"):
                                    moment["end_anchor"] = matched_cand["end_anchor"]

                                if item.get("why_clip_worthy"):
                                    moment["why_clip_worthy"] = item["why_clip_worthy"]
                                elif matched_cand and matched_cand.get("why_clip_worthy"):
                                    moment["why_clip_worthy"] = matched_cand["why_clip_worthy"]

                                if matched_cand and matched_cand.get("start_time"):
                                    moment["start_time"] = matched_cand["start_time"]
                                if matched_cand and matched_cand.get("end_time"):
                                    moment["end_time"] = matched_cand["end_time"]

                                curated_moments.append(moment)

                            logger.info(f"  > Model B critique completed: {len(curated_moments)} curated moments (from {len(parsed_a)} candidates).")
                            chunk_outlines = curated_moments
                        else:
                            logger.warning("  > Model B critique returned invalid/empty response. Falling back to Model A candidates.")
                            chunk_outlines = parsed_a

                    except Exception as crit_err:
                        logger.warning(f"  > Model B critique failed ({crit_err}). Falling back to Model A candidates.")
                        chunk_outlines = parsed_a

                elif not parsed_a and model_b and model_b != model_a:
                    # Model A returned empty, query Model B directly as fallback extractor
                    logger.info(f"  > Model A returned empty. Querying Model B '{model_b}' directly as fallback extractor...")
                    try:
                        response_b = self.llm_client.call_with_retry(
                            self.outline_prompt, input_data, task="moment_extraction", model=model_b
                        )
                        parsed_b = self._parse_outline_response(response_b, chunk_idx) if response_b else []
                        for p in parsed_b:
                            p['source_model'] = model_b
                            p['confidence'] = "unverified"
                        chunk_outlines = parsed_b
                        logger.info(f"  > Fallback extractor Model B found {len(chunk_outlines)} moments.")
                    except Exception as fb_err:
                        logger.warning(f"  > Fallback extractor Model B failed: {fb_err}")
                        chunk_outlines = []
                else:
                    chunk_outlines = parsed_a

                if tracker:
                    models_summary = f"{model_a} + {model_b} critique" if (model_b and model_b != model_a) else model_a
                    tracker.log(f"Chunk {chunk_idx + 1}: found {len(chunk_outlines)} moments ({models_summary})")

                if not chunk_outlines:
                    logger.warning(f"Processing chunk {chunk_idx+1}: No moments extracted across models.")
            except Exception as e:
                logger.error(f"Processing chunk {chunk_idx+1} failed: {e}")
            return chunk_idx, chunk_outlines

        workers = max(1, min(len(chunk_files), LLM_MAX_PARALLEL_CHUNKS))
        logger.info(f"[AutoClip] Processing {len(chunk_files)} chunks with ThreadPoolExecutor (max_workers={workers})...")

        chunk_results_by_idx = {}
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_process_single_chunk, i, chunk_file): i
                for i, chunk_file in enumerate(chunk_files)
            }
            for future in as_completed(futures):
                idx, results = future.result()
                chunk_results_by_idx[idx] = results

        # Preserve deterministic chunk order before deduplication and ensembling
        for i in range(len(chunk_files)):
            if i in chunk_results_by_idx:
                all_outlines.extend(chunk_results_by_idx[i])
        
        # 5. Ensembling, timestamp overlap merging, confidence tagging, and duplicate guard
        final_outlines = self._ensemble_and_deduplicate_moments(all_outlines, srt_data=srt_data)
        
        logger.info(f"Outline extraction complete, total {len(final_outlines)} high-retention moments finalized.")
        return final_outlines

    def _save_chunks_to_files(self, chunks: List[Dict]) -> List[Path]:
        """Saves text blocks as individual .txt files"""
        chunk_files = []
        for chunk in chunks:
            chunk_index = chunk['chunk_index']
            text_content = chunk['text']
            file_path = self.chunks_dir / f"chunk_{chunk_index}.txt"
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(text_content)
            chunk_files.append(file_path)
        
        logger.info(f"All text blocks saved to: {self.chunks_dir}")
        return chunk_files

    def _save_srt_chunks(self, chunks: List[Dict]):
        """Saves SRT data blocks as individual .json files"""
        for chunk in chunks:
            chunk_index = chunk['chunk_index']
            srt_entries = chunk['srt_entries']
            file_path = self.srt_chunks_dir / f"chunk_{chunk_index}.json"
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(srt_entries, f, ensure_ascii=False, indent=2)
        
        logger.info(f"All SRT blocks saved to: {self.srt_chunks_dir}")

    def _parse_outline_response(self, response: str, chunk_index: int) -> List[Dict]:
        """
        Parses the model's outline response supporting JSON arrays, Markdown lists, and fallback text blocks.
        """
        if not response or not response.strip():
            return []

        # 1. Attempt structured JSON parsing
        try:
            parsed_json = self.llm_client.parse_json_response(response)
            if isinstance(parsed_json, list) and len(parsed_json) > 0:
                json_outlines = []
                for item in parsed_json:
                    if isinstance(item, dict):
                        title = item.get("title") or item.get("outline") or item.get("topic") or item.get("hook")
                        if not title:
                            continue
                        subtopics = []
                        for k in [
                            "subtopics", "content", "points", "insights", "insight", "punchline", "hook",
                            "money_quote", "guest_insight", "actionability", "the_verdict", "why_urgent",
                            "the_take", "support", "lesson", "setup", "conflict", "resolution",
                            "character_revealed", "topic", "why_clip_worthy"
                        ]:
                            val = item.get(k)
                            if isinstance(val, list):
                                subtopics.extend([str(x).strip() for x in val if str(x).strip()])
                            elif isinstance(val, str) and val.strip():
                                subtopics.append(val.strip())
                        outline_item = {
                            'title': str(title).strip(),
                            'subtopics': subtopics,
                            'chunk_index': chunk_index,
                            'category': item.get('category') or self.category
                        }
                        for field_name in ['id', 'start_anchor', 'end_anchor', 'why_clip_worthy', 'start_time', 'end_time']:
                            if item.get(field_name):
                                outline_item[field_name] = item[field_name]
                        json_outlines.append(outline_item)
                if json_outlines:
                    logger.info(f"Successfully parsed {len(json_outlines)} outlines from structured JSON")
                    return json_outlines
        except Exception as json_err:
            logger.debug(f"JSON outline parse attempt bypassed: {json_err}")

        # 2. Markdown / Text list parsing
        outlines = []
        lines = response.split('\n')
        current_outline = None
        
        for line in lines:
            sline = line.strip()
            if not sline:
                continue
            
            # Match 1. **Title**, 1. Title, ### 1. Title, **1. Title**, or "text": "question"
            num_match = re.match(r'^(?:#+\s*)?(?:\*\s*)?(?:\*\*)?(\d+)[\.\)]\s*(?:\*\*)?(.*?)(?:\*\*)?$', sline)
            json_text_match = re.match(r'^["\']?text["\']?\s*:\s*["\']([^"\']+)["\']', sline)

            if num_match and num_match.group(2).strip():
                if current_outline:
                    outlines.append(current_outline)
                topic_name = num_match.group(2).strip().strip('*').strip()
                current_outline = {
                    'title': topic_name,
                    'subtopics': [],
                    'chunk_index': chunk_index,
                    'category': self.category
                }
            elif json_text_match and json_text_match.group(1).strip():
                if current_outline:
                    outlines.append(current_outline)
                topic_name = json_text_match.group(1).strip()
                current_outline = {
                    'title': topic_name,
                    'subtopics': [],
                    'chunk_index': chunk_index,
                    'category': self.category
                }
            elif sline.startswith(('-', '*', '•')) and current_outline:
                subtopic = sline.lstrip('-*• ').strip()
                if subtopic and len(subtopic) <= 300:
                    current_outline['subtopics'].append(subtopic)
        
        if current_outline:
            outlines.append(current_outline)
        
        logger.info(f"Extracted {len(outlines)} outlines from text/markdown")
        return outlines
    
    def _ensemble_and_deduplicate_moments(self, all_candidates: List[Dict], srt_data: Optional[List[Dict]] = None) -> List[Dict]:
        """
        Deduplicates candidate moments from multiple models using timestamp overlap:
        - When two models extract moments that overlap by >= 50%, merge them into one moment.
        - Keep the more descriptive title / outline summary.
        - Tag each moment with confidence:
          * confidence: "high" (found by 2 or 3 models)
          * confidence: "low" (found by 1 model)
        - Duplicate guard: After merging, assert that no two moments in the final list
          overlap by > 50%. If any do, keep the one with higher confidence (or longer duration)
          and log a warning.
        """
        if not all_candidates:
            return []

        import re

        def _to_sec(val: Any) -> float:
            if not val:
                return 0.0
            try:
                return self.text_processor.time_to_seconds(str(val))
            except Exception:
                return 0.0

        def _get_interval(item: Dict) -> Tuple[float, float]:
            """Returns (start_sec, end_sec) for an outline moment."""
            st_str = item.get('start_time')
            et_str = item.get('end_time')
            if st_str and et_str:
                s = _to_sec(st_str)
                e = _to_sec(et_str)
                if e > s:
                    return s, e

            # Search in SRT cues using title keywords
            if srt_data:
                title_words = [w for w in re.findall(r'\w+', str(item.get('title', '')).lower()) if len(w) > 3]
                matched_cues = []
                for cue in srt_data:
                    cue_text = str(cue.get('text', '')).lower()
                    if any(w in cue_text for w in title_words):
                        matched_cues.append(cue)
                if matched_cues:
                    s = _to_sec(matched_cues[0].get('start_time'))
                    e = _to_sec(matched_cues[-1].get('end_time'))
                    if e > s:
                        return s, max(s + 30.0, e)

            # Fallback: estimate from chunk_index
            ci = item.get('chunk_index', 0)
            base_sec = float(ci * 1800)
            return base_sec, base_sec + 60.0

        def _overlap_ratio(i1: Tuple[float, float], i2: Tuple[float, float]) -> float:
            s1, e1 = i1
            s2, e2 = i2
            inter = max(0.0, min(e1, e2) - max(s1, s2))
            if inter <= 0:
                return 0.0
            min_dur = min(max(1.0, e1 - s1), max(1.0, e2 - s2))
            return inter / min_dur

        # Initialize tracking on candidates
        processed: List[Dict] = []
        for c in all_candidates:
            c_copy = dict(c)
            source_model = c_copy.get('source_model', 'unknown')
            c_copy['models_found'] = {source_model}
            c_copy['interval'] = _get_interval(c_copy)
            processed.append(c_copy)

        # Merge overlapping moments (>= 50% overlap or same topic in same chunk)
        merged: List[Dict] = []
        for cand in processed:
            matched = False
            for target in merged:
                ratio = _overlap_ratio(cand['interval'], target['interval'])
                t1_clean = str(cand.get('title', '')).strip().lower()
                t2_clean = str(target.get('title', '')).strip().lower()
                title_match = (
                    cand.get('chunk_index') == target.get('chunk_index') and
                    (t1_clean == t2_clean or (len(t1_clean) > 8 and t1_clean in t2_clean) or (len(t2_clean) > 8 and t2_clean in t1_clean))
                )

                if ratio >= 0.50 or title_match:
                    # Merge into target
                    target['models_found'].update(cand['models_found'])
                    # Combine subtopics
                    t_subs = target.get('subtopics', [])
                    c_subs = cand.get('subtopics', [])
                    target['subtopics'] = list(dict.fromkeys(t_subs + c_subs))
                    # Expand interval
                    s_min = min(target['interval'][0], cand['interval'][0])
                    e_max = max(target['interval'][1], cand['interval'][1])
                    target['interval'] = (s_min, e_max)
                    # Prefer more descriptive title
                    if len(str(cand.get('title', ''))) > len(str(target.get('title', ''))):
                        target['title'] = cand['title']
                    matched = True
                    break

            if not matched:
                merged.append(cand)

        # Tag confidence
        for m in merged:
            num_models = len(m['models_found'])
            existing_conf = m.get('confidence')
            if existing_conf and existing_conf in ('validated', 'added', 'unverified'):
                m['confidence'] = existing_conf
            else:
                m['confidence'] = "high" if num_models >= 2 else "low"
            m['models_count'] = num_models
            m['models_found'] = list(m['models_found'])
            st, et = m['interval']
            if 'start_time' not in m or not m['start_time']:
                m['start_time'] = self.text_processor.seconds_to_time(st)
            if 'end_time' not in m or not m['end_time']:
                m['end_time'] = self.text_processor.seconds_to_time(et)
            m.pop('interval', None)

        # Duplicate guard: assert no two remaining moments overlap by > 50%
        # If any do, keep the one with higher confidence (or longer duration if equal)
        guarded = self._apply_duplicate_guard(merged)
        logger.info(f"[Step 1 Ensembling] Extracted {len(guarded)} moments after deduplication and duplicate guard.")
        return guarded

    def _apply_duplicate_guard(self, moments: List[Dict]) -> List[Dict]:
        """
        Duplicate guard: After merging, assert that no two moments in the final list
        overlap by > 50%. If any do, keep the one with higher confidence (or longer duration if equal)
        and log a warning.
        """
        if not moments:
            return []

        def _to_sec(val: Any) -> float:
            if not val:
                return 0.0
            try:
                return self.text_processor.time_to_seconds(str(val))
            except Exception:
                return 0.0

        def _overlap_ratio(i1: Tuple[float, float], i2: Tuple[float, float]) -> float:
            s1, e1 = i1
            s2, e2 = i2
            inter = max(0.0, min(e1, e2) - max(s1, s2))
            if inter <= 0:
                return 0.0
            min_dur = min(max(1.0, e1 - s1), max(1.0, e2 - s2))
            return inter / min_dur

        guarded: List[Dict] = []
        for item in moments:
            item_int = (_to_sec(item.get('start_time')), _to_sec(item.get('end_time')))
            duplicate = False
            for existing in list(guarded):
                ex_int = (_to_sec(existing.get('start_time')), _to_sec(existing.get('end_time')))
                ratio = _overlap_ratio(item_int, ex_int)
                if ratio > 0.50:
                    duplicate = True
                    item_conf_score = 2 if item.get('confidence') in ('high', 'validated') else 1
                    ex_conf_score = 2 if existing.get('confidence') in ('high', 'validated') else 1
                    
                    if item_conf_score > ex_conf_score:
                        logger.warning(
                            f"Duplicate guard triggered: replacing low-confidence '{existing.get('title')}' "
                            f"with high-confidence duplicate '{item.get('title')}' (overlap: {ratio:.1%})"
                        )
                        guarded.remove(existing)
                        guarded.append(item)
                    elif item_conf_score == ex_conf_score:
                        item_dur = max(0.0, item_int[1] - item_int[0])
                        ex_dur = max(0.0, ex_int[1] - ex_int[0])
                        if item_dur > ex_dur:
                            logger.warning(
                                f"Duplicate guard triggered: replacing shorter '{existing.get('title')}' "
                                f"with longer duplicate '{item.get('title')}' (overlap: {ratio:.1%})"
                            )
                            guarded.remove(existing)
                            guarded.append(item)
                        else:
                            logger.warning(
                                f"Duplicate guard triggered: discarded duplicate moment '{item.get('title')}' "
                                f"overlapping {ratio:.1%} with '{existing.get('title')}'"
                            )
                    else:
                        logger.warning(
                            f"Duplicate guard triggered: discarded low-confidence duplicate '{item.get('title')}' "
                            f"overlapping {ratio:.1%} with '{existing.get('title')}'"
                        )
                    break

            if not duplicate:
                guarded.append(item)

        return guarded

    def _merge_outlines(self, outlines: List[Dict]) -> List[Dict]:
        """Backwards compatibility delegator to ensembling deduplication."""
        return self._ensemble_and_deduplicate_moments(outlines)
    
    def save_outline(self, outlines: List[Dict], output_path: Optional[Path] = None) -> Path:
        """
        Saves outline to file
        """
        if output_path is None:
            output_path = self.metadata_dir / "step1_outline.json"
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(outlines, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Outline saved to: {output_path}")
        return output_path
    
    def load_outline(self, input_path: Path) -> List[Dict]:
        """
        Loads outline from file
        """
        with open(input_path, 'r', encoding='utf-8') as f:
            return json.load(f)

def run_step1_outline(
    srt_path: Path, 
    metadata_dir: Path = None, 
    output_path: Optional[Path] = None, 
    prompt_files: Dict = None, 
    category: str = "default",
    tracker: Optional[Any] = None
) -> List[Dict]:
    """
    Runs Step 1: Outline Extraction with Category-Aware Duration Windows
    """
    if metadata_dir is None:
        metadata_dir = METADATA_DIR
        
    extractor = OutlineExtractor(metadata_dir=metadata_dir, prompt_files=prompt_files, category=category)
    outlines = extractor.extract_outline(srt_path, tracker=tracker)
    
    if output_path is None:
        output_path = metadata_dir / "step1_outline.json"
        
    extractor.save_outline(outlines, output_path)
    
    return outlines