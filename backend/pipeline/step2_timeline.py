import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Any

from ..core.shared_config import (
    METADATA_DIR,
    PROMPT_FILES,
    get_clip_duration_limits,
    get_prompt_files
)
from ..utils.llm_client import LLMClient
from ..utils.text_processor import TextProcessor

logger = logging.getLogger(__name__)

class TimelineExtractor:
    """Step 2: Topic Timeline Extraction (extract start and end timestamps)"""

    def __init__(self, metadata_dir: Path = None, prompt_files: Dict = None, category: str = "default"):
        self.metadata_dir = metadata_dir or METADATA_DIR
        self.category = category
        self.prompt_files = prompt_files or get_prompt_files(self.category)
        self.llm_client = LLMClient()
        self.text_processor = TextProcessor()
        
        # Load prompt file
        self.timeline_prompt = self._load_prompt()
        
        # Intermediate and output directories
        self.srt_chunks_dir = self.metadata_dir / "step1_srt_chunks"
        self.timeline_chunks_dir = self.metadata_dir / "step2_timeline_chunks"
        self.llm_raw_output_dir = self.metadata_dir / "step2_llm_raw_output"

    def _load_prompt(self) -> str:
        """Load prompt template"""
        prompt_path = self.prompt_files.get('timeline')
        if not prompt_path or not prompt_path.exists():
            raise FileNotFoundError(f"Timeline prompt file not found: {prompt_path}")
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()

    def _split_srt_into_subchunks(
        self,
        srt_entries: List[Dict],
        max_chars: int = 18000,
        overlap_entries: int = 15
    ) -> List[List[Dict]]:
        """
        Splits SRT entries into sub-chunks where each sub-chunk's serialized
        text stays safely under the max_chars character budget.
        Includes overlap_entries between adjacent sub-chunks so boundaries are not severed.
        """
        if not srt_entries:
            return []

        subchunks: List[List[Dict]] = []
        current_subchunk: List[Dict] = []
        current_chars = 0

        for sub in srt_entries:
            entry_str = f"{sub.get('index')}\n{sub.get('start_time')} --> {sub.get('end_time')}\n{sub.get('text', '')}\n\n"
            entry_chars = len(entry_str)

            if current_subchunk and (current_chars + entry_chars > max_chars):
                subchunks.append(current_subchunk)
                overlap_slice = current_subchunk[-overlap_entries:] if len(current_subchunk) >= overlap_entries else current_subchunk
                current_subchunk = list(overlap_slice)
                current_chars = sum(
                    len(f"{s.get('index')}\n{s.get('start_time')} --> {s.get('end_time')}\n{s.get('text', '')}\n\n")
                    for s in current_subchunk
                )

            current_subchunk.append(sub)
            current_chars += entry_chars

        if current_subchunk:
            subchunks.append(current_subchunk)

        return subchunks

    def _get_cue_start_sec(self, cue: Dict) -> float:
        try:
            return self.text_processor.time_to_seconds(self._convert_time_format(cue.get('start_time', '00:00:00')))
        except Exception:
            return 0.0

    def _get_cue_end_sec(self, cue: Dict) -> float:
        try:
            return self.text_processor.time_to_seconds(self._convert_time_format(cue.get('end_time', '00:00:00')))
        except Exception:
            return 0.0

    def _deduplicate_and_merge_items(self, items: List[Dict]) -> List[Dict]:
        """
        Deduplicates timeline items produced by multiple overlapping subchunks.
        If the same topic title appears multiple times:
        - If their time intervals overlap or are contiguous (gap <= 5s), merge them.
        - If their intervals are separated, keep both as distinct topic moments.
        """
        if not items:
            return []

        # Sort by start_time
        def _get_sec(t_str: str) -> float:
            try:
                return self.text_processor.time_to_seconds(self._convert_time_format(t_str))
            except Exception:
                return 0.0

        sorted_items = sorted(items, key=lambda x: _get_sec(x.get('start_time', '00:00:00')))
        merged: List[Dict] = []

        for item in sorted_items:
            item_topic = item.get('outline', '')
            if isinstance(item_topic, dict):
                item_topic = item_topic.get('title', '')
            item_start = _get_sec(item.get('start_time', '00:00:00'))
            item_end = _get_sec(item.get('end_time', '00:00:00'))

            found_overlap = False
            for existing in merged:
                exist_topic = existing.get('outline', '')
                if isinstance(exist_topic, dict):
                    exist_topic = exist_topic.get('title', '')
                exist_start = _get_sec(existing.get('start_time', '00:00:00'))
                exist_end = _get_sec(existing.get('end_time', '00:00:00'))

                # Same topic and intervals overlap or within 5 seconds of each other
                if item_topic.strip().lower() == exist_topic.strip().lower() and not (item_end < exist_start - 5.0 or item_start > exist_end + 5.0):
                    # Merge boundaries
                    new_start = min(exist_start, item_start)
                    new_end = max(exist_end, item_end)
                    existing['start_time'] = self.text_processor.seconds_to_time(new_start)
                    existing['end_time'] = self.text_processor.seconds_to_time(new_end)
                    # Merge content bullets
                    existing_content = existing.get('content', [])
                    if isinstance(existing_content, list):
                        new_content = item.get('content', [])
                        if isinstance(new_content, list):
                            existing['content'] = list(dict.fromkeys(existing_content + new_content))
                    found_overlap = True
                    break

            if not found_overlap:
                merged.append(item)

        return merged

    def extract_timeline(self, outlines: List[Dict], category: Optional[str] = None, tracker: Optional[Any] = None) -> List[Dict]:
        """
        Extract topic time intervals.
        - Sub-chunks SRT blocks by character budget to guarantee no context limit overflow.
        - Runs provider-aware LLM calls with retry.
        - Repairs undersized clip boundaries to complete thought resolution.
        - Deduplicates and merges overlapping results.
        - Fails loudly if unrecoverable errors occur instead of silently outputting empty JSON.
        """
        if category:
            self.category = category
        logger.info("Beginning to extract topic time intervals...")
        
        if not outlines:
            logger.warning("Outline data is empty, unable to extract timeline.")
            return []

        self.timeline_chunks_dir.mkdir(parents=True, exist_ok=True)
        self.llm_raw_output_dir.mkdir(parents=True, exist_ok=True)

        # Fast path check: Do all outlines already possess valid timestamps?
        has_predefined_timestamps = all(
            bool(o.get('start_time') and o.get('end_time') and self._validate_time_format(str(o['start_time'])) and self._validate_time_format(str(o['end_time'])))
            for o in outlines
        )
        if has_predefined_timestamps and len(outlines) > 0:
            logger.info(f"Fast path: {len(outlines)} outlines already contain validated start/end timestamps. Bypassing LLM timeline search.")
            if tracker:
                tracker.log(f"Fast path: localized {len(outlines)} timeline intervals directly from discovered moments")

            min_dur, max_dur = get_clip_duration_limits(self.category)
            timeline_items = []
            for i, o in enumerate(outlines):
                s_fmt = self._convert_time_format(str(o['start_time']))
                e_fmt = self._convert_time_format(str(o['end_time']))
                s_sec = self.text_processor.time_to_seconds(s_fmt)
                e_sec = self.text_processor.time_to_seconds(e_fmt)
                dur = e_sec - s_sec
                if dur < min_dur:
                    e_sec = s_sec + min_dur
                elif dur > max_dur:
                    e_sec = s_sec + max_dur

                t_item = {
                    "id": str(i + 1),
                    "start_time": self.text_processor.seconds_to_time(s_sec),
                    "end_time": self.text_processor.seconds_to_time(e_sec),
                    "outline": o.get("title") or o.get("outline", f"Moment {i+1}"),
                    "content": o.get("subtopics") or o.get("content") or [],
                    "chunk_index": o.get("chunk_index", 0),
                    "confidence": o.get("confidence", "validated"),
                    "category": o.get("category", self.category)
                }
                timeline_items.append(t_item)

            chunk_0_path = self.timeline_chunks_dir / "chunk_0.json"
            with open(chunk_0_path, 'w', encoding='utf-8') as f:
                json.dump(timeline_items, f, ensure_ascii=False, indent=2)

            return timeline_items

        if not self.srt_chunks_dir.exists():
            raise FileNotFoundError(
                f"SRT block directory does not exist: {self.srt_chunks_dir}. Step 1 must run first."
            )

        # Group all outlines by chunk_index
        outlines_by_chunk = defaultdict(list)
        for outline in outlines:
            chunk_index = outline.get('chunk_index')
            if chunk_index is not None:
                outlines_by_chunk[chunk_index].append(outline)
            else:
                logger.warning(f"  > Topic '{outline.get('title', 'Unknown')}' missing chunk_index, default to chunk 0.")
                outlines_by_chunk[0].append(outline)

        all_timeline_data = []
        max_srt_chars = getattr(self.llm_client, "get_max_srt_chars", lambda: 18000)()
        logger.info(f"Using provider-aware Step 2 character budget: {max_srt_chars} chars per subchunk")

        last_error_message = None

        total_chunks = len(outlines_by_chunk)
        for chunk_order, (chunk_index, chunk_outlines) in enumerate(outlines_by_chunk.items(), 1):
            logger.info(f"Processing chunk {chunk_index} ({len(chunk_outlines)} topics)...")
            if tracker:
                tracker.set_substep(
                    f"Chunk {chunk_order} of {total_chunks} ({len(chunk_outlines)} topics)",
                    current=chunk_order,
                    total=total_chunks
                )
            chunk_output_path = self.timeline_chunks_dir / f"chunk_{chunk_index}.json"

            srt_chunk_path = self.srt_chunks_dir / f"chunk_{chunk_index}.json"
            if not srt_chunk_path.exists():
                logger.warning(f"  > SRT block file not found: {srt_chunk_path}, skipping chunk.")
                continue

            with open(srt_chunk_path, 'r', encoding='utf-8') as f:
                srt_chunk_data = json.load(f)

            if not srt_chunk_data:
                logger.warning(f"  > SRT block file is empty: {srt_chunk_path}, skipping chunk.")
                continue

            # Split srt_chunk_data into sub-chunks if needed to stay within character budget
            subchunks = self._split_srt_into_subchunks(srt_chunk_data, max_chars=max_srt_chars, overlap_entries=15)
            logger.info(f"  > Chunk {chunk_index} split into {len(subchunks)} sub-chunk(s) to respect context limits.")

            chunk_extracted_items: List[Dict] = []

            for sub_idx, sub_entries in enumerate(subchunks):
                sub_start_time = sub_entries[0]['start_time']
                sub_end_time = sub_entries[-1]['end_time']
                sub_srt_text = "".join(
                    f"{sub['index']}\n{sub['start_time']} --> {sub['end_time']}\n{sub['text']}\n\n"
                    for sub in sub_entries
                )

                logger.info(
                    f"  > Sub-chunk {sub_idx + 1}/{len(subchunks)} "
                    f"({sub_start_time} -> {sub_end_time}, {len(sub_srt_text)} chars)..."
                )

                llm_input_outlines = [
                    {
                        "id": str(idx + 1),
                        "outline": o.get("title") or o.get("outline"),
                        "content": o.get("subtopics") or o.get("content") or []
                    }
                    for idx, o in enumerate(chunk_outlines)
                ]

                input_data = {
                    "outline": llm_input_outlines,
                    "srt_text": sub_srt_text
                }

                if len(subchunks) > 1:
                    input_data["additional_instruction"] = (
                        f"\n\n[CRITICAL SUB-SEGMENT INSTRUCTION]:\n"
                        f"This subtitle excerpt only covers a PORTION of the video ({sub_start_time} to {sub_end_time}).\n"
                        "1. ONLY output topics that have their primary discussion and complete thought resolution within this excerpt.\n"
                        "2. If a topic is not discussed or only briefly referenced in passing without reaching its resolution, DO NOT force an entry — OMIT IT completely.\n"
                        "3. Do NOT output micro-snippets (under 25s) just to match an outline item; only output when a genuine, complete narrative arc exists here."
                    )

                parsed_items = None
                max_parse_retries = 2

                for retry_count in range(max_parse_retries + 1):
                    try:
                        raw_response = self.llm_client.call_with_retry(self.timeline_prompt, input_data)
                        if not raw_response:
                            logger.warning(f"  > Sub-chunk {sub_idx} LLM response empty, skipping attempt.")
                            continue

                        cache_file = self.llm_raw_output_dir / f"chunk_{chunk_index}_sub_{sub_idx}_attempt_{retry_count}.txt"
                        with open(cache_file, 'w', encoding='utf-8') as f:
                            f.write(raw_response)

                        parsed_items = self._parse_and_validate_response(
                            raw_response,
                            sub_start_time,
                            sub_end_time,
                            chunk_index,
                            srt_chunk_data=srt_chunk_data
                        )

                        if parsed_items:
                            # Propagate confidence and category from Step 1 outline
                            for pi in parsed_items:
                                pi_outline_name = str(pi.get('outline', '')).strip().lower()
                                for co in chunk_outlines:
                                    co_name = str(co.get('title') or co.get('outline', '')).strip().lower()
                                    if co_name == pi_outline_name or (len(co_name) > 5 and co_name in pi_outline_name) or (len(pi_outline_name) > 5 and pi_outline_name in co_name):
                                        if 'confidence' in co:
                                            pi['confidence'] = co['confidence']
                                        if 'category' in co:
                                            pi['category'] = co['category']
                                        break
                            logger.info(f"  > Sub-chunk {sub_idx + 1} successfully parsed {len(parsed_items)} moments.")
                            chunk_extracted_items.extend(parsed_items)
                            break
                        else:
                            if retry_count < max_parse_retries:
                                logger.warning(f"  > Sub-chunk {sub_idx + 1} parse returned 0 valid items, retrying ({retry_count + 1}/{max_parse_retries + 1})...")
                                input_data['additional_instruction'] = (
                                    "\n\n[Important] Output requirements: \n"
                                    "1. Return a JSON array matching [{\"id\": ..., \"start_time\": \"HH:MM:SS,mmm\", \"end_time\": \"HH:MM:SS,mmm\", \"outline\": ..., \"content\": [...]}]\n"
                                    "2. Use double quotes and strictly valid JSON syntax."
                                )

                    except Exception as parse_error:
                        last_error_message = str(parse_error)
                        logger.error(f"  > Sub-chunk {sub_idx + 1} attempt {retry_count + 1} error: {parse_error}")
                        if retry_count == max_parse_retries:
                            self._save_debug_response(
                                raw_response if 'raw_response' in locals() else str(parse_error),
                                chunk_index,
                                f"sub_{sub_idx}_parse_exception"
                            )

            # Deduplicate and merge items across all subchunks in this chunk
            merged_chunk_items = self._deduplicate_and_merge_items(chunk_extracted_items)
            logger.info(f"  > Chunk {chunk_index} total extracted moments after deduplication: {len(merged_chunk_items)}")
            if tracker:
                tracker.log(f"Timeline chunk {chunk_index}: extracted {len(merged_chunk_items)} intervals")

            if merged_chunk_items:
                with open(chunk_output_path, 'w', encoding='utf-8') as f:
                    json.dump(merged_chunk_items, f, ensure_ascii=False, indent=2)

        # Read back all chunk output files
        chunk_files = sorted(list(self.timeline_chunks_dir.glob("chunk_*.json")))
        for cf in chunk_files:
            try:
                with open(cf, 'r', encoding='utf-8') as f:
                    cdata = json.load(f)
                    if isinstance(cdata, list):
                        all_timeline_data.extend(cdata)
            except Exception as e:
                logger.error(f"Failed to read chunk file {cf}: {e}")

        # Merge adjacent or consecutive segments sharing the same topic across chunks
        if all_timeline_data:
            all_timeline_data = self.merge_adjacent_segments(all_timeline_data, category=self.category)

        # Loud failure check: If outlines existed, but timeline extraction extracted nothing
        if outlines and not all_timeline_data:
            error_details = (
                f"Step 2 timeline extraction failed to identify any valid clip intervals from "
                f"{len(outlines)} outlines across {len(outlines_by_chunk)} chunk(s). "
                f"Last error: {last_error_message or 'No timeline moments located in subtitles'}."
            )
            logger.critical(error_details)
            raise RuntimeError(error_details)

        # Global sort by start time and assign clean sequential IDs
        if all_timeline_data:
            try:
                all_timeline_data.sort(
                    key=lambda x: self.text_processor.time_to_seconds(
                        self._convert_time_format(x.get('start_time', '00:00:00'))
                    )
                )
                for i, it in enumerate(all_timeline_data):
                    it['id'] = str(i + 1)
                logger.info(f"Step 2 complete: allocated {len(all_timeline_data)} sequential clip IDs (1-{len(all_timeline_data)})")
            except Exception as e:
                logger.error(f"Error while sorting final results: {e}. Returning unsorted.")

        return all_timeline_data

    def merge_adjacent_segments(self, timeline_data: List[Dict], category: Optional[str] = None) -> List[Dict]:
        """
        Merge adjacent or consecutive segments that share the same topic/moment.
        Allows merged segments to span multiple chunks up to the category's max duration.
        """
        if not timeline_data or len(timeline_data) <= 1:
            return timeline_data

        def _get_sec(t_str: str) -> float:
            try:
                return self.text_processor.time_to_seconds(self._convert_time_format(t_str))
            except Exception:
                return 0.0

        min_dur, max_dur = get_clip_duration_limits(category or self.category)
        sorted_items = sorted(timeline_data, key=lambda x: _get_sec(x.get('start_time', '00:00:00')))

        merged: List[Dict] = []
        for item in sorted_items:
            if not merged:
                merged.append(item)
                continue

            prev = merged[-1]
            prev_topic = prev.get('outline', '')
            if isinstance(prev_topic, dict):
                prev_topic = prev_topic.get('title', '')
            curr_topic = item.get('outline', '')
            if isinstance(curr_topic, dict):
                curr_topic = curr_topic.get('title', '')

            prev_start = _get_sec(prev.get('start_time', '00:00:00'))
            prev_end = _get_sec(prev.get('end_time', '00:00:00'))
            curr_start = _get_sec(item.get('start_time', '00:00:00'))
            curr_end = _get_sec(item.get('end_time', '00:00:00'))

            # Check topic equivalence, base title match, or containment
            pt_clean = str(prev_topic).strip().lower()
            ct_clean = str(curr_topic).strip().lower()
            import re
            base_p = re.sub(r'\(part \d+\)|\(pt \d+\)|part \d+|pt \d+', '', pt_clean).strip()
            base_c = re.sub(r'\(part \d+\)|\(pt \d+\)|part \d+|pt \d+', '', ct_clean).strip()
            is_same_topic = (
                pt_clean == ct_clean or
                (len(base_p) > 5 and base_p == base_c) or
                (len(pt_clean) > 5 and pt_clean in ct_clean) or
                (len(ct_clean) > 5 and ct_clean in pt_clean)
            )

            # Check temporal adjacency: overlapping or gap <= 15.0 seconds
            is_adjacent = curr_start <= (prev_end + 15.0) and curr_end >= prev_start
            potential_duration = max(prev_end, curr_end) - min(prev_start, curr_start)

            if is_same_topic and is_adjacent and potential_duration <= max_dur:
                # Merge into previous segment
                new_start = min(prev_start, curr_start)
                new_end = max(prev_end, curr_end)
                prev['start_time'] = f"{self.text_processor.seconds_to_time(new_start)},000"
                prev['end_time'] = f"{self.text_processor.seconds_to_time(new_end)},000"
                
                # Combine content lists
                prev_content = prev.get('content', []) or []
                curr_content = item.get('content', []) or []
                if isinstance(prev_content, list) and isinstance(curr_content, list):
                    prev['content'] = list(dict.fromkeys(prev_content + curr_content))
                
                # Prefer more descriptive title
                if len(str(curr_topic)) > len(str(prev_topic)):
                    prev['outline'] = curr_topic

                logger.info(
                    f"  > Merged adjacent segments for '{prev_topic}' across boundaries: "
                    f"duration expanded to {potential_duration:.1f}s"
                )
            else:
                merged.append(item)

        return merged

    def _repair_short_clip_boundary(
        self,
        timeline_item: Dict,
        start_sec: float,
        raw_end_sec: float,
        chunk_end_sec: float,
        srt_data: Optional[List[Dict]],
        min_dur: float,
        max_dur: float
    ) -> float:
        """
        Repairs an undersized clip (< min_dur) by finding its true narrative resolution
        rather than blindly padding with an arbitrary fixed time offset.

        1. Attempts LLM repair by inspecting the next 60-90s of transcript to find the exact
           timestamp where the story/thought finishes.
        2. Fallback: Extends to the first subsequent SRT cue ending at or after start_sec + min_dur
           that terminates on natural punctuation (., !, ?) or conversational silence.
        3. If no natural resolution can be found within bounds, marks needs_review: true.
        """
        raw_dur = max(0.0, raw_end_sec - start_sec)
        topic_name = timeline_item.get('outline', 'Unknown Topic')
        if isinstance(topic_name, dict):
            topic_name = topic_name.get('title', 'Unknown Topic')
        content = timeline_item.get('content', [])

        logger.warning(
            f"  > Clip '{topic_name}' raw duration ({raw_dur:.1f}s) is below "
            f"minimum threshold ({min_dur:.1f}s). Initiating narrative resolution repair..."
        )

        # 1. Attempt LLM repair if subtitle cues are available
        if srt_data:
            window_end = min(chunk_end_sec, start_sec + max_dur)
            window_cues = [
                c for c in srt_data 
                if (start_sec - 0.5) <= self._get_cue_start_sec(c) <= window_end
            ]
            if len(window_cues) >= 2:
                continuation_srt = "".join(
                    f"{c.get('index', i+1)}\n{c.get('start_time')} --> {c.get('end_time')}\n{c.get('text', '')}\n\n"
                    for i, c in enumerate(window_cues)
                )
                start_time_str = self.text_processor.seconds_to_time(start_sec)
                end_time_str = self.text_processor.seconds_to_time(raw_end_sec)

                repair_prompt = (
                    "You are an expert video editor repairing a prematurely truncated clip.\n"
                    f"Topic: {topic_name}\n"
                    f"Expected Key Points / Payoff: {content}\n\n"
                    f"The proposed clip currently starts at {start_time_str} and prematurely cuts off after only {raw_dur:.1f}s ({end_time_str}), "
                    "ending prematurely before the speaker completes their thought/story.\n\n"
                    "Here is the transcript continuing from the start of the clip:\n"
                    f"{continuation_srt}\n\n"
                    f"Identify the EXACT timestamp ('end_time' in HH:MM:SS,mmm format) where this story, argument, or dialogue "
                    f"reaches its natural resolution, conclusion, or punchline (must be at least {min_dur:.0f}s from {start_time_str}).\n"
                    "Output strictly JSON:\n"
                    "{\"end_time\": \"HH:MM:SS,mmm\", \"resolution_found\": true}"
                )

                try:
                    raw_repair = self.llm_client.call_with_retry(repair_prompt, max_retries=1)
                    parsed_repair = self.llm_client.parse_json_response(raw_repair)
                    if isinstance(parsed_repair, dict) and parsed_repair.get("resolution_found"):
                        rep_end_str = parsed_repair.get("end_time")
                        if rep_end_str and self._validate_time_format(rep_end_str):
                            rep_end_sec = self.text_processor.time_to_seconds(self._convert_time_format(rep_end_str))
                            if rep_end_sec >= (start_sec + min_dur) and rep_end_sec <= min(chunk_end_sec, start_sec + max_dur):
                                logger.info(
                                    f"  > Successfully repaired short clip '{topic_name}' boundary "
                                    f"from {raw_dur:.1f}s to {rep_end_sec - start_sec:.1f}s at narrative resolution."
                                )
                                return rep_end_sec
                except Exception as e:
                    logger.debug(f"LLM boundary repair bypassed: {e}")

        # 2. Sentence-aligned fallback: find cue at or after start_sec + min_dur ending on punctuation
        if srt_data:
            for i, c in enumerate(srt_data):
                cue_end = self._get_cue_end_sec(c)
                if (start_sec + min_dur) <= cue_end <= (start_sec + min_dur + 30.0):
                    cue_text = str(c.get('text', '')).strip()
                    ends_punc = bool(cue_text and cue_text[-1] in ".!?。！？…")
                    has_gap = False
                    if i + 1 < len(srt_data):
                        next_start = self._get_cue_start_sec(srt_data[i + 1])
                        has_gap = (next_start - cue_end) >= 0.35

                    if ends_punc or has_gap:
                        adjusted_end = min(chunk_end_sec, cue_end + 0.12)
                        logger.warning(
                            f"  > Clip '{topic_name}' raw duration ({raw_dur:.1f}s) extended via "
                            f"sentence-aligned fallback to {adjusted_end - start_sec:.1f}s at natural sentence end."
                        )
                        return adjusted_end

        # 3. Last-resort fallback: clamp to min_dur and flag needs_review
        adjusted_end = min(chunk_end_sec, start_sec + min_dur)
        timeline_item['needs_review'] = True
        logger.warning(
            f"  > Clip '{topic_name}' could not reach a clean sentence conclusion within bounds. "
            f"Padded to {adjusted_end - start_sec:.1f}s and marked needs_review: true."
        )
        return adjusted_end

    def _parse_and_validate_response(
        self,
        response: str,
        chunk_start: str,
        chunk_end: str,
        chunk_index: int,
        srt_chunk_data: Optional[List[Dict]] = None
    ) -> List[Dict]:
        """Enhanced parsing of LLM response, validates and adjusts time"""
        validated_items = []
        self._save_debug_response(response, chunk_index, "original_response")

        try:
            parsed_response = self.llm_client.parse_json_response(response)
            if not isinstance(parsed_response, list):
                logger.warning(f"  > Block {chunk_index} LLM returned non-list type: {type(parsed_response)}")
                return []

            chunk_start_sec = self.text_processor.time_to_seconds(self._convert_time_format(chunk_start))
            chunk_end_sec = self.text_processor.time_to_seconds(self._convert_time_format(chunk_end))
            min_dur, max_dur = get_clip_duration_limits(self.category)

            for timeline_item in parsed_response:
                if not isinstance(timeline_item, dict):
                    continue
                if 'outline' not in timeline_item or 'start_time' not in timeline_item or 'end_time' not in timeline_item:
                    continue

                timeline_item['chunk_index'] = chunk_index

                if not self._validate_time_format(timeline_item['start_time']) or not self._validate_time_format(timeline_item['end_time']):
                    logger.warning(f"  > Invalid timestamp format: {timeline_item.get('start_time')} -> {timeline_item.get('end_time')}")
                    continue

                start_time_fmt = self._convert_time_format(timeline_item['start_time'])
                end_time_fmt = self._convert_time_format(timeline_item['end_time'])

                start_sec = self.text_processor.time_to_seconds(start_time_fmt)
                end_sec = self.text_processor.time_to_seconds(end_time_fmt)

                # If LLM returned relative chunk timestamps (e.g. chunk starts at 3600s, but LLM output 00:00:10 -> 00:02:00)
                if chunk_start_sec > 0 and start_sec < chunk_start_sec:
                    if end_sec < chunk_start_sec:
                        start_sec = chunk_start_sec + start_sec
                        end_sec = chunk_start_sec + end_sec
                    else:
                        start_sec = chunk_start_sec + start_sec

                # Clamp within enclosing chunk bounds
                start_sec = max(chunk_start_sec, min(chunk_end_sec - 1.0, start_sec))
                end_sec = min(chunk_end_sec, max(start_sec + 1.0, end_sec))

                raw_duration = end_sec - start_sec
                topic_name = timeline_item.get('outline', 'Unknown Topic')
                if isinstance(topic_name, dict):
                    topic_name = topic_name.get('title', 'Unknown Topic')

                # Adjust if below minimum or above maximum
                if raw_duration < min_dur:
                    repaired_end_sec = self._repair_short_clip_boundary(
                        timeline_item=timeline_item,
                        start_sec=start_sec,
                        raw_end_sec=end_sec,
                        chunk_end_sec=chunk_end_sec,
                        srt_data=srt_chunk_data,
                        min_dur=min_dur,
                        max_dur=max_dur
                    )
                    end_sec = repaired_end_sec
                elif raw_duration > max_dur:
                    clamped_end = min(chunk_end_sec, start_sec + max_dur)
                    clamped_dur = clamped_end - start_sec
                    logger.warning(
                        f"  > Clip '{topic_name}' raw duration ({raw_duration:.1f}s) exceeds "
                        f"maximum threshold ({max_dur:.1f}s). Clamped to {clamped_dur:.1f}s."
                    )
                    end_sec = clamped_end
                else:
                    logger.info(f"  > Clip '{topic_name}' preserved natural duration: {raw_duration:.1f}s")

                timeline_item['start_time'] = self.text_processor.seconds_to_time(start_sec)
                timeline_item['end_time'] = self.text_processor.seconds_to_time(end_sec)
                validated_items.append(timeline_item)

            return validated_items

        except Exception as e:
            logger.error(f"  > Block {chunk_index} error during parsing response: {e}")
            return []

    def _validate_time_format(self, time_str: str) -> bool:
        """Validates if time format is recognizable (HH:MM:SS,mmm or HH:MM:SS.mmm or HH:MM:SS:mmm or HH:MM:SS)"""
        if not time_str or not isinstance(time_str, str):
            return False
        time_str = time_str.strip()
        pattern = r'^\d{1,2}:\d{2}:\d{2}(?:[,.:]\d{1,3})?$'
        return bool(re.match(pattern, time_str))

    def _convert_time_format(self, time_str: str) -> str:
        """Converts time format to standard FFmpeg format HH:MM:SS.mmm"""
        if not time_str or time_str == "end":
            return time_str
        time_str = time_str.strip()
        m = re.match(r'^(\d{1,2}):(\d{2}):(\d{2})(?:[,.:](\d{1,3}))?$', time_str)
        if m:
            h_int = int(m.group(1))
            mn_int = int(m.group(2))
            s_int = int(m.group(3))
            ms = m.group(4)
            ms_int = int(ms.ljust(3, '0')) if ms else 0
            return f"{h_int:02d}:{mn_int:02d}:{s_int:02d}.{ms_int:03d}"
        return time_str.replace(',', '.')

    def _save_debug_response(self, response: str, chunk_index: int, error_type: str) -> None:
        """Saves debug response to file"""
        try:
            debug_dir = self.metadata_dir / "debug_responses"
            debug_dir.mkdir(parents=True, exist_ok=True)
            debug_file = debug_dir / f"chunk_{chunk_index}_{error_type}.txt"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(response)
        except Exception as e:
            logger.error(f"Saving debug response failed: {e}")

    def save_timeline(self, timeline_data: List[Dict], output_path: Optional[Path] = None) -> Path:
        """Saves timeline data to disk"""
        if output_path is None:
            output_path = METADATA_DIR / "step2_timeline.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(timeline_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Timeline data saved to: {output_path}")
        return output_path

    def load_timeline(self, input_path: Path) -> List[Dict]:
        """Loads timeline data from file"""
        with open(input_path, 'r', encoding='utf-8') as f:
            return json.load(f)

def run_step2_timeline(
    outline_path: Path,
    metadata_dir: Path = None,
    output_path: Optional[Path] = None,
    prompt_files: Dict = None,
    category: str = "default",
    tracker: Optional[Any] = None
) -> List[Dict]:
    """Run Step 2: Time point extraction with loud failure guarantee."""
    if metadata_dir is None:
        metadata_dir = METADATA_DIR

    extractor = TimelineExtractor(metadata_dir, prompt_files, category=category)

    outlines = []
    outline_p = Path(outline_path)
    if outline_p.exists() and outline_p.stat().st_size > 2:
        try:
            with open(outline_p, 'r', encoding='utf-8') as f:
                outlines = json.load(f)
        except json.JSONDecodeError as jde:
            logger.warning(f"Failed to load outline from {outline_path}: {jde}")
            outlines = []

    timeline_data = extractor.extract_timeline(outlines, category=category, tracker=tracker)

    if outlines and not timeline_data:
        raise RuntimeError(
            f"Step 2 failed to produce timeline intervals from {len(outlines)} outlines. Pipeline aborted."
        )

    if output_path is None:
        output_path = metadata_dir / "step2_timeline.json"

    extractor.save_timeline(timeline_data, output_path)

    # Ensure step2_words.json is preserved/mirrored in metadata_dir if companion words exist
    try:
        step2_words_file = metadata_dir / "step2_words.json"
        if not step2_words_file.exists():
            for cand in [metadata_dir / "words.json", metadata_dir / "input_words.json", outline_path.parent / "words.json", outline_path.parent / "step2_words.json"]:
                if cand.exists():
                    import shutil
                    shutil.copyfile(cand, step2_words_file)
                    logger.info(f"[AutoClip] Mirrored companion words to {step2_words_file}")
                    break
    except Exception as e:
        logger.debug(f"Companion words preservation skipped: {e}")

    return timeline_data
