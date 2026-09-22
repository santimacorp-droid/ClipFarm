"""
Step 4: Title Generation - Generate Engaging Titles for High-Quality Content
"""
import json
import logging
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from collections import defaultdict

# Importing dependencies
from ..utils.llm_client import LLMClient
from ..utils.text_processor import TextProcessor
from ..core.shared_config import PROMPT_FILES, METADATA_DIR

logger = logging.getLogger(__name__)

class TitleGenerator:
    """Title Generator"""
    
    def __init__(self, metadata_dir: Optional[Path] = None, prompt_files: Dict = None):
        self.llm_client = LLMClient()
        self.text_processor = TextProcessor()
        
        # Load prompt words
        prompt_files_to_use = prompt_files if prompt_files is not None else PROMPT_FILES
        with open(prompt_files_to_use['title'], 'r', encoding='utf-8') as f:
            self.title_prompt = f.read()
        
        # Use the provided metadata_dir or default value
        if metadata_dir is None:
            metadata_dir = METADATA_DIR
        self.metadata_dir = metadata_dir
        self.llm_raw_output_dir = self.metadata_dir / "step4_llm_raw_output"
    
    def generate_titles(self, high_score_clips: List[Dict], category: str = "general") -> List[Dict]:
        """
        Generate titles for high-score clips (New: Batch processing by chunk with cache addition))
        """
        if not high_score_clips:
            return []
            
        logger.info(f"Beginning to generate titles for {len(high_score_clips)} Batch generating titles for high-score fragments (category={category})...")
        
        self.llm_raw_output_dir.mkdir(parents=True, exist_ok=True)
        
        from ..utils.hook_generator import ensure_hook_has_color_emojis, clean_hook_markup

        clips_by_chunk = defaultdict(list)
        for clip in high_score_clips:
            if not clip.get('category') or clip.get('category') == 'default':
                clip['category'] = category
            clips_by_chunk[clip.get('chunk_index', 0)].append(clip)
            
        all_clips_with_titles = []
        for chunk_index, chunk_clips in clips_by_chunk.items():
            logger.info(f"Processing block {chunk_index}, which contains {len(chunk_clips)} segments...")
            
            try:
                logger.info(f"  > Starting API call to generate title...")
                input_for_llm = [
                    {
                        "id": clip.get('id'),
                        "title": clip.get('outline'),  # Use the 'outline' field as the topic title
                        "content": clip.get('content'),
                        "category": clip.get('category') or category,
                        "recommend_reason": clip.get('recommend_reason'),
                        "what_makes_this_distinctive": clip.get('what_makes_this_distinctive') or clip.get('recommend_reason')
                    } for clip in chunk_clips
                ]
                
                try:
                    raw_response = self.llm_client.call_with_retry(self.title_prompt, input_for_llm, task="titling")
                except TypeError:
                    raw_response = self.llm_client.call_with_retry(self.title_prompt, input_for_llm)
                
                if raw_response:
                    # Save LLM original response for debugging (but don't use as cache)
                    llm_cache_path = self.llm_raw_output_dir / f"chunk_{chunk_index}.txt"
                    with open(llm_cache_path, 'w', encoding='utf-8') as f:
                        f.write(raw_response)
                    logger.info(f"  > LLMOriginal response saved to {llm_cache_path}")
                    titles_map = self.llm_client.parse_json_response(raw_response)
                else:
                    titles_map = {}
                
                if not isinstance(titles_map, dict):
                    logger.warning(f"  > LLMReturned title is not a dictionary: {titles_map}, Skipped this block. ")
                    # Even if it fails, re-add the original segment to avoid data loss
                    all_clips_with_titles.extend(chunk_clips)
                    continue

                for clip in chunk_clips:
                    clip_id = clip.get('id')
                    clip_result = titles_map.get(clip_id)
                    if clip_result is None and clip_id is not None:
                        clip_result = titles_map.get(str(clip_id))
                    if clip_result is None and isinstance(clip_id, str) and clip_id.isdigit():
                        clip_result = titles_map.get(int(clip_id))

                    clip_cat = clip.get('category') or category

                    if clip_result:
                        if isinstance(clip_result, dict):
                            # New format: {title, hook}
                            clip['generated_title'] = clean_hook_markup(clip_result.get('title') or '').strip()
                            hook = (clip_result.get('hook') or '').strip()
                            # Fallback: full title if hook is missing
                            if not hook and clip['generated_title']:
                                hook = clip['generated_title']
                            clip['hook_text'] = ensure_hook_has_color_emojis(hook, category=clip_cat)
                        elif isinstance(clip_result, str):
                            # Old format fallback (backward compat)
                            clip['generated_title'] = clean_hook_markup(clip_result.strip())
                            clip['hook_text'] = ensure_hook_has_color_emojis(clip_result.strip(), category=clip_cat)
                    else:
                        outline = clip.get('outline')
                        if isinstance(outline, dict):
                            clip['generated_title'] = outline.get('title', f"Segment_{clip_id}")
                        else:
                            clip['generated_title'] = str(outline) if outline else f"Segment_{clip_id}"
                        clip['hook_text'] = ensure_hook_has_color_emojis(clip['generated_title'], category=clip_cat)

                    # Maintain hook_title for downstream compatibility
                    clip['hook_title'] = clip.get('hook_text', '')

                    logger.info(f"  > For segment {clip_id}: title='{clip['generated_title']}', hook='{clip['hook_text']}'")
                
                all_clips_with_titles.extend(chunk_clips)

            except Exception as e:
                logger.error(f"  > For block {chunk_index} Error occurred while generating titles: {e}")
                # Even if there's an error, add original data to prevent data loss
                all_clips_with_titles.extend(chunk_clips)
                continue
                
        logger.info("All high-scoring segment titles generated successfully")

        # Generate rich context-aware social posting captions and hashtags
        try:
            from ..utils.social_caption_generator import SocialCaptionGenerator
            caption_gen = SocialCaptionGenerator(llm_client=self.llm_client)
            
            # Retrieve project outlines and srt from metadata_dir
            outlines = []
            if self.metadata_dir:
                outline_file = self.metadata_dir / "step1_outline.json"
                if outline_file.exists():
                    try:
                        with open(outline_file, 'r', encoding='utf-8') as f:
                            outlines = json.load(f)
                    except Exception:
                        pass
            
            srt_path = None
            if self.metadata_dir:
                cand_srts = [
                    self.metadata_dir / "input.srt",
                    self.metadata_dir.parent / "raw" / "input.srt"
                ]
                for cs in cand_srts:
                    if cs.exists():
                        srt_path = cs
                        break

            global_context = {
                "video_title": self.metadata_dir.parent.name if (self.metadata_dir and self.metadata_dir.parent) else "Full Video",
                "video_category": category,
                "outlines": outlines
            }
            
            caption_gen.batch_generate_social_captions(
                clips=all_clips_with_titles,
                global_context=global_context,
                srt_path=srt_path
            )
            logger.info(f"Generated social captions & hashtags for {len(all_clips_with_titles)} clips")
        except Exception as cap_err:
            logger.warning(f"Social caption generation skipped in Step 4: {cap_err}")

        return all_clips_with_titles
        
    def save_clips_with_titles(self, clips_with_titles: List[Dict], output_path: Path):
        """Saving title-enhanced segment data"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(clips_with_titles, f, ensure_ascii=False, indent=2)
        logger.info(f"Titles added to segments. Data saved to: {output_path}")

def run_step4_title(high_score_clips_path: Path, metadata_dir: Path = None, output_path: Optional[Path] = None, prompt_files: Dict = None, category: str = "default") -> List[Dict]:
    """
    Run Step 4: Title Generation and Optimization

    Args:
        high_score_clips_path: Path to high-score clip file
        output_path: Output file path, default is step4_titles.json
        metadata_dir: Directory path for metadata
        prompt_files: Custom prompt files
        category: Video classification category ('business', 'knowledge', etc.)

    Returns:
        List of title-enhanced clips
    """
    # Load high-scoring segments
    with open(high_score_clips_path, 'r', encoding='utf-8') as f:
        high_score_clips = json.load(f)

    # Resolve prompt files by category if not explicitly provided
    if prompt_files is None:
        from ..core.shared_config import get_prompt_files
        prompt_files = get_prompt_files(category)

    # Create title generator
    if metadata_dir is None:
        metadata_dir = METADATA_DIR
    title_generator = TitleGenerator(metadata_dir=Path(metadata_dir), prompt_files=prompt_files)
    
    # Generating title
    clips_with_titles = title_generator.generate_titles(high_score_clips, category=category)
    
    # Confirm Output Path
    if metadata_dir is None:
        metadata_dir = METADATA_DIR
    
    if output_path is None:
        output_path = Path(metadata_dir) / "step4_titles.json"
        
    # Save title-enhanced segment data tostep4_titles.json
    title_generator.save_clips_with_titles(clips_with_titles, output_path)
    
    # Important Notice: clips_metadata.json will be saved in Step 6, avoid duplicate saving here.
    # This prevents data duplication and confusion in save logic
    
    return clips_with_titles