import logging
import re
import uuid
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import pysrt
from pysrt import SubRipItem, SubRipTime

logger = logging.getLogger(__name__)

class SubtitleProcessor:
    """Subtitle processor – supports subtitle parsing and processing at character granularity"""
    
    def __init__(self):
        # Tokenizer separators: punctuation and whitespace characters.
        self.word_separators = r"[,.!?;:\s]+"
    
    def parse_srt_to_word_level(self, srt_path: Path) -> List[Dict]:
        """
        Parses SRT subtitles into a data structure with word-level timestamps.
        
        Args:
            srt_path: Path to SRT file
            
        Returns:
            Subtitles data in character-level
        """
        if not srt_path.exists():
            logger.error(f"SRTFile not found: {srt_path}")
            return []
        
        try:
            subs = pysrt.open(str(srt_path), encoding='utf-8')
            raw_segments = []
            
            for sub in subs:
                segment_data = self._process_subtitle_segment(sub)
                if segment_data.get('text'):
                    raw_segments.append(segment_data)
            
            # Sort by start time and resolve overlaps
            raw_segments.sort(key=lambda s: s['startTime'])
            word_level_data = []
            for i, seg in enumerate(raw_segments):
                st = seg['startTime']
                et = seg['endTime']
                if i < len(raw_segments) - 1:
                    next_st = raw_segments[i + 1]['startTime']
                    if et > next_st and next_st > st:
                        et = next_st
                        seg['endTime'] = et
                if et > st:
                    word_level_data.append(seg)
            
            logger.info(f"Successfully parsed SRT file, containing {len(word_level_data)} subtitle fragments (time overlap eliminated automatically))")
            return word_level_data
            
        except Exception as e:
            logger.error(f"Parsing SRT file failed.: {e}")
            return []
    
    def _process_subtitle_segment(self, sub: SubRipItem) -> Dict:
        """
        Processes a single subtitle fragment, breaking it down into character-level data.
        
        Args:
            sub: pysrtSubtitle item
            
        Returns:
            Character-level subtitles data
        """
        # Converting time format
        start_seconds = self._srt_time_to_seconds(sub.start)
        end_seconds = self._srt_time_to_seconds(sub.end)
        
        # Splitting text into words
        words = self._split_text_to_words(sub.text, start_seconds, end_seconds)
        
        return {
            'id': str(uuid.uuid4()),
            'startTime': start_seconds,
            'endTime': end_seconds,
            'text': sub.text.strip(),
            'words': words,
            'index': sub.index
        }
    
    def _split_text_to_words(self, text: str, start_time: float, end_time: float) -> List[Dict]:
        """
        Breaks down text into words and assigns time stamps.
        
        Args:
            text: Subtitle text
            start_time: Start time (seconds)
            end_time: End time (seconds)
            
        Returns:
            List of words, each containing a time stamp.
        """
        # Cleaning text
        clean_text = text.strip()
        if not clean_text:
            return []
        
        # Split by punctuation and spaces.
        word_parts = re.split(self.word_separators, clean_text)
        word_parts = [part.strip() for part in word_parts if part.strip()]
        
        if not word_parts:
            return []
        
        # Calculates time allocation for each word.
        total_duration = end_time - start_time
        words_count = len(word_parts)
        
        # Simple time distribution strategy: equal allocation.
        word_duration = total_duration / words_count
        
        words = []
        for i, word_text in enumerate(word_parts):
            word_start = start_time + (i * word_duration)
            word_end = word_start + word_duration
            
            words.append({
                'id': str(uuid.uuid4()),
                'text': word_text,
                'startTime': word_start,
                'endTime': word_end
            })
        
        return words
    
    def _srt_time_to_seconds(self, srt_time: SubRipTime) -> float:
        """
        Convert SRT time format to seconds.
        
        Args:
            srt_time: pysrtTime object
            
        Returns:
            Seconds
        """
        return srt_time.hours * 3600 + srt_time.minutes * 60 + srt_time.seconds + srt_time.milliseconds / 1000
    
    def _seconds_to_srt_time_object(self, time_str: str) -> SubRipTime:
        """
        Convert a time string to a pysrt time object.
        
        Args:
            time_str: Time string (e.g. "00:01:25,140")
            
        Returns:
            pysrtTime object
        """
        # Processing comma and dot formats
        time_str = time_str.replace(',', '.')
        
        # Parsing time
        time_parts = time_str.split(':')
        hours = int(time_parts[0])
        minutes = int(time_parts[1])
        
        # Processing seconds and milliseconds
        seconds_part = time_parts[2]
        if '.' in seconds_part:
            seconds, milliseconds = seconds_part.split('.')
            seconds = int(seconds)
            milliseconds = int(milliseconds.ljust(3, '0')[:3])  # Ensuring 3 digits for milliseconds
        else:
            seconds = int(seconds_part)
            milliseconds = 0
        
        return SubRipTime(hours, minutes, seconds, milliseconds)
    
    def create_edit_operations(self, deleted_segments: List[str], 
                             original_data: List[Dict]) -> List[Dict]:
        """
        Creates edit operations from deleted subtitle fragments.
        
        Args:
            deleted_segments: List of subtitle fragment IDs to be deleted.
            original_data: Original subtitle data
            
        Returns:
            List of editing operations
        """
        operations = []
        
        for segment_id in deleted_segments:
            segment = next((s for s in original_data if s['id'] == segment_id), None)
            if segment:
                operation = {
                    'type': 'delete',
                    'segmentIds': [segment_id],
                    'timestamp': segment['startTime'],
                    'metadata': {
                        'originalText': segment['text'],
                        'timeRange': {
                            'start': segment['startTime'],
                            'end': segment['endTime']
                        }
                    }
                }
                operations.append(operation)
        
        return operations
    
    def generate_edited_video_timeline(self, original_data: List[Dict], 
                                     deleted_segments: List[str]) -> List[Tuple[float, float]]:
        """
        Generates an edited video timeline.
        
        Args:
            original_data: Original subtitle data
            deleted_segments: List of subtitle fragment IDs to be deleted.
            
        Returns:
            List of retained fragment time ranges. [(start, end), ...]
        """
        deleted_ids = set(deleted_segments)
        timeline = []
        
        for segment in original_data:
            if segment['id'] not in deleted_ids:
                timeline.append((segment['startTime'], segment['endTime']))
        
        # Merging adjacent time intervals
        if timeline:
            merged_timeline = [timeline[0]]
            for current_start, current_end in timeline[1:]:
                last_start, last_end = merged_timeline[-1]
                
                # If the current fragment is adjacent to or overlaps with the previous one, merge them.
                if current_start <= last_end + 0.1:  # Allowing 0.1 second interval
                    merged_timeline[-1] = (last_start, max(last_end, current_end))
                else:
                    merged_timeline.append((current_start, current_end))
            
            return merged_timeline
        
        return []
    
    def export_edited_srt(self, original_data: List[Dict], 
                         deleted_segments: List[str], 
                         output_path: Path) -> bool:
        """
        Exports edited SRT file.
        
        Args:
            original_data: Original subtitle data
            deleted_segments: List of subtitle fragment IDs to be deleted.
            output_path: Output file path
            
        Returns:
            Whether succeeded
        """
        try:
            deleted_ids = set(deleted_segments)
            edited_segments = []
            
            for segment in original_data:
                if segment['id'] not in deleted_ids:
                    edited_segments.append(segment)
            
            # Re-numbering
            for i, segment in enumerate(edited_segments, 1):
                segment['index'] = i
            
            # Writing to SRT file
            with open(output_path, 'w', encoding='utf-8') as f:
                for segment in edited_segments:
                    start_time = self._seconds_to_srt_time(segment['startTime'])
                    end_time = self._seconds_to_srt_time(segment['endTime'])
                    
                    f.write(f"{segment['index']}\n")
                    f.write(f"{start_time} --> {end_time}\n")
                    f.write(f"{segment['text']}\n\n")
            
            logger.info(f"Edited SRT file saved successfully.: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Exporting edited SRT file failed.: {e}")
            return False
    
    def _seconds_to_srt_time(self, seconds: float) -> str:
        """
        Convert seconds to SRT time format.
        
        Args:
            seconds: Seconds
            
        Returns:
            SRTTime format string
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"
    
    def get_subtitle_statistics(self, data: List[Dict]) -> Dict:
        """
        Getting subtitle statistics information
        
        Args:
            data: Subtitle data
            
        Returns:
            Statistics information
        """
        if not data:
            return {
                'totalDuration': 0,
                'wordCount': 0,
                'segmentCount': 0,
                'averageWordsPerSegment': 0
            }
        
        total_duration = max(seg['endTime'] for seg in data) - min(seg['startTime'] for seg in data)
        word_count = sum(len(seg['words']) for seg in data)
        segment_count = len(data)
        
        return {
            'totalDuration': total_duration,
            'wordCount': word_count,
            'segmentCount': segment_count,
            'averageWordsPerSegment': word_count / segment_count if segment_count > 0 else 0
        }
