"""
Step 5: Topic Clustering - Cluster similar content into thematic collections
"""
import json
import logging
import re
from typing import List, Dict, Any, Optional
from pathlib import Path

# Dependencies
from ..utils.llm_client import LLMClient
from ..core.shared_config import PROMPT_FILES, METADATA_DIR, MAX_CLIPS_PER_COLLECTION

logger = logging.getLogger(__name__)

class ClusteringEngine:
    """Topic clustering engine"""
    
    def __init__(self, metadata_dir: Optional[Path] = None, prompt_files: Dict = None):
        self.llm_client = LLMClient()
        
        # Loading prompts
        prompt_files_to_use = prompt_files if prompt_files is not None else PROMPT_FILES
        with open(prompt_files_to_use['clustering'], 'r', encoding='utf-8') as f:
            self.clustering_prompt = f.read()
        
        # Use provided metadata_dir or default value
        if metadata_dir is None:
            metadata_dir = METADATA_DIR
        self.metadata_dir = metadata_dir
    
    def cluster_clips(self, clips_with_titles: List[Dict]) -> List[Dict]:
        """
        Cluster topics on segments
        
        Args:
            clips_with_titles: List of segment titles
            
        Returns:
            List of collection data
        """
        logger.info("Starting topic clustering...")
        
        # Prepare clustering data
        clips_for_clustering = []
        for clip in clips_with_titles:
            clips_for_clustering.append({
                'id': clip['id'],
                'title': clip.get('generated_title', clip['outline']),
                'summary': clip.get('recommend_reason', ''),
                'score': clip.get('final_score', 0)
            })
        
        # First perform keyword-based pre-clustering
        pre_clusters = self._pre_cluster_by_keywords(clips_for_clustering)
        
        # Build complete prompt
        full_prompt = self.clustering_prompt + "\n\nHere is a list of video clips: \n"
        for i, clip in enumerate(clips_for_clustering, 1):
            full_prompt += f"{i}. Title: {clip['title']}\n   Summary: {clip['summary']}\n   Score: {clip['score']:.2f}\n\n"
        
        # Add pre-clustering result as reference
        if pre_clusters:
            full_prompt += "\n\nKeyword-based pre-clustering reference: \n"
            for theme, clip_ids in pre_clusters.items():
                full_prompt += f"{theme}: {', '.join(clip_ids)}\n"
        
        try:
            # Call LLM for clustering
            response = self.llm_client.call_with_retry(full_prompt)
            
            # Parse JSON response
            collections_data = self.llm_client.parse_json_response(response)
            
            # Validate and clean collection data
            validated_collections = self._validate_collections(collections_data, clips_with_titles)
            
            # Fallback to pre-clusters if LLM collections are insufficient
            if len(validated_collections) < 3:
                logger.warning("LLM clustering returned insufficient collections; using pre-clustering fallback")
                validated_collections = self._create_collections_from_pre_clusters(pre_clusters, clips_with_titles)
            
            logger.info(f"Topic clustering complete: generated {len(validated_collections)} collections")
            return validated_collections
            
        except Exception as e:
            logger.error(f"Topic clustering failed: {str(e)}")
            # Use pre-clustering results as backup
            if pre_clusters:
                logger.info("Using pre-clustering results as alternative fallback")
                return self._create_collections_from_pre_clusters(pre_clusters, clips_with_titles)
            # Return default collections fallback
            return self._create_default_collections(clips_with_titles)
    
    def _pre_cluster_by_keywords(self, clips: List[Dict]) -> Dict[str, List[str]]:
        """
        Pre-cluster by keywords
        
        Args:
            clips: List of segments
            
        Returns:
            Pre-clustering results
        """
        # Define topic keywords
        theme_keywords = {
            'Investment & Finance': ['investment', 'wealth', 'stocks', 'funds', 'trading', 'profit', 'yield', 'revenue', 'portfolio', 'nasdaq', 'market', 'crypto', 'finance'],
            'Career & Growth': ['workplace', 'career', 'skills', 'learning', 'leadership', 'executive', 'education', 'college', 'productivity', 'resume', 'interviews'],
            'Social Commentary': ['society', 'culture', 'internet', 'media', 'trends', 'algorithms', 'platform', 'mechanisms', 'creators', 'industry'],
            'Cultural Perspectives': ['culture', 'differences', 'global', 'travel', 'food', 'language', 'tradition', 'lifestyle', 'foreign', 'customs'],
            'Interactive & Streaming': ['livestream', 'interaction', 'chat', 'audience', 'community', 'donations', 'giveaway', 'gaming', 'highlights'],
            'Relationships & Psychology': ['dating', 'emotion', 'social', 'relationships', 'psychology', 'attraction', 'communication', 'mindset', 'conflict'],
            'Health & Wellness': ['health', 'fitness', 'running', 'nutrition', 'diet', 'lifestyle', 'workout', 'mental health', 'sleep', 'energy'],
            'Content Creation': ['creation', 'platforms', 'youtube', 'tiktok', 'instagram', 'photography', 'content', 'growth', 'editing', 'production']
        }
        
        pre_clusters = {theme: [] for theme in theme_keywords.keys()}
        
        for clip in clips:
            # Merge title and summary for keyword matching
            text = f"{clip['title']} {clip['summary']}".lower()
            
            # Calculate match score for each theme
            theme_scores = {}
            for theme, keywords in theme_keywords.items():
                score = sum(1 for keyword in keywords if keyword in text)
                if score > 0:
                    theme_scores[theme] = score
            
            # Select theme with highest match score
            if theme_scores:
                best_theme = max(theme_scores.keys(), key=lambda k: theme_scores[k])
                pre_clusters[best_theme].append(clip['id'])
        
        # Filter out empty themes
        return {theme: clip_ids for theme, clip_ids in pre_clusters.items() if len(clip_ids) >= 2}
    
    def _create_collections_from_pre_clusters(self, pre_clusters: Dict[str, List[str]], clips_with_titles: List[Dict]) -> List[Dict]:
        """
        Create collection from pre-clustering results

        Args:
            pre_clusters: Pre-clustering results
            clips_with_titles: Clip data

        Returns:
            List of collection data
        """
        collections = []
        collection_id = 1
        
        # Thematic Title Mapping
        theme_titles = {
            'Investment & Finance': 'Investment & Wealth Insights',
            'Career & Growth': 'Career & Professional Growth', 
            'Social Commentary': 'Social Observations & Trends',
            'Cultural Perspectives': 'Global Cultural Perspectives',
            'Interactive & Streaming': 'Live Interaction Highlights',
            'Relationships & Psychology': 'Emotions & Relationship Dynamics',
            'Health & Wellness': 'Health & Wellness Habits',
            'Content Creation': 'Content Creation & Ecosystem'
        }
        
        # Topic summary mapping
        theme_summaries = {
            'Investment & Finance': 'Key investment frameworks and financial market perspectives.',
            'Career & Growth': 'Career growth strategies, skills acceleration, and workplace mindset.',
            'Social Commentary': 'Insightful commentary on contemporary society and digital media trends.',
            'Cultural Perspectives': 'Cross-cultural discussions, international lifestyles, and diverse perspectives.',
            'Interactive & Streaming': 'High-energy live streaming moments and creator-audience engagement.',
            'Relationships & Psychology': 'Deep dives into emotional intelligence, psychology, and relationships.',
            'Health & Wellness': 'Practical advice on physical conditioning, nutrition, and mental health.',
            'Content Creation': 'Behind-the-scenes creator playbooks, platform growth, and media production.'
        }
        
        for theme, clip_ids in pre_clusters.items():
            # Limit clips per collection
            if len(clip_ids) > MAX_CLIPS_PER_COLLECTION:
                clip_ids = clip_ids[:MAX_CLIPS_PER_COLLECTION]
            
            collections.append({
                'id': str(collection_id),
                'collection_title': theme_titles.get(theme, theme),
                'collection_summary': theme_summaries.get(theme, f'{theme} curated highlight collection'),
                'clip_ids': clip_ids
            })
            collection_id += 1
        
        return collections
    
    def _validate_collections(self, collections_data: List[Dict], clips_with_titles: List[Dict]) -> List[Dict]:
        """
        Validate and clean collection data

Args:
    collections_data: Original collection data
    clips_with_titles: Clip data

Returns:
    Validated collection data
        """
        validated_collections = []
        
        for i, collection in enumerate(collections_data):
            try:
                # Validate mandatory fields
                if not all(key in collection for key in ['collection_title', 'collection_summary', 'clips']):
                    logger.warning(f"Collection {i} missing required fields, skipping")
                    continue
                
                # Validate clip list
                clip_titles = collection['clips']
                valid_clip_ids = []
                
                for clip_title in clip_titles:
                    # Match clip ID by title
                    for clip in clips_with_titles:
                        if (clip.get('generated_title', clip['outline']) == clip_title or 
                            clip['outline'] == clip_title):
                            valid_clip_ids.append(clip['id'])
                            break
                
                if len(valid_clip_ids) < 2:
                    logger.warning(f"Collection {i} has fewer than 2 valid clips, skipping")
                    continue
                
                # Limit clips per collection
                if len(valid_clip_ids) > MAX_CLIPS_PER_COLLECTION:
                    valid_clip_ids = valid_clip_ids[:MAX_CLIPS_PER_COLLECTION]
                
                validated_collection = {
                    'id': str(i + 1),
                    'collection_title': collection['collection_title'],
                    'collection_summary': collection['collection_summary'],
                    'clip_ids': valid_clip_ids
                }
                
                validated_collections.append(validated_collection)
                
            except Exception as e:
                logger.error(f"Failed to validate collection {i}: {str(e)}")
                continue
        
        return validated_collections
    
    def _create_default_collections(self, clips_with_titles: List[Dict]) -> List[Dict]:
        """
        Create default collections (fallback when clustering fails)
        
        Args:
            clips_with_titles: Clip data
            
        Returns:
            Default collections data
        """
        logger.info("Creating default collections fallback...")
        
        # Group by rating
        high_score = []
        medium_score = []
        
        for clip in clips_with_titles:
            score = clip.get('final_score', 0)
            if score >= 0.8:
                high_score.append(clip)
            elif score >= 0.6:
                medium_score.append(clip)
        
        collections = []
        
        # Create high-score collection
        if len(high_score) >= 2:
            collections.append({
                'id': '1',
                'collection_title': 'Top Viral Highlights',
                'collection_summary': 'Curated collection of highest-scoring viral segments',
                'clip_ids': [clip['id'] for clip in high_score[:MAX_CLIPS_PER_COLLECTION]]
            })
        
        # Create medium-score collection
        if len(medium_score) >= 2:
            collections.append({
                'id': '2',
                'collection_title': 'Recommended Highlights',
                'collection_summary': 'Curated collection of valuable highlight segments',
                'clip_ids': [clip['id'] for clip in medium_score[:MAX_CLIPS_PER_COLLECTION]]
            })
        
        return collections
    
    def save_collections(self, collections_data: List[Dict], output_path: Optional[Path] = None) -> Path:
        """
        Save collection data

        Args:
            collections_data: Collection data
            output_path: Output path

        Returns:
            Saved file path
        """
        if output_path is None:
            output_path = self.metadata_dir / "collections.json"
        
        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save data
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(collections_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Collection data saved to: {output_path}")
        return output_path
    
    def load_collections(self, input_path: Path) -> List[Dict]:
        """
        Load collection data from file

        Args:
            input_path: Input file path

        Returns:
            Collection data
        """
        with open(input_path, 'r', encoding='utf-8') as f:
            return json.load(f)

def run_step5_clustering(clips_with_titles_path: Path, output_path: Optional[Path] = None, metadata_dir: Optional[str] = None, prompt_files: Dict = None) -> List[Dict]:
    """
    Run Step 5: Topic Clustering

    Args:
        clips_with_titles_path: Path to clip file with titles
        output_path: Output file path
        prompt_files: Custom prompt files
        
    Returns:
        Combined data
    """
    # Load data
    with open(clips_with_titles_path, 'r', encoding='utf-8') as f:
        clips_with_titles = json.load(f)
    
    # Create clustering engine
    if metadata_dir is None:
        metadata_dir = METADATA_DIR
    clusterer = ClusteringEngine(metadata_dir=Path(metadata_dir), prompt_files=prompt_files)
    
    # Perform clustering
    collections_data = clusterer.cluster_clips(clips_with_titles)
    
    # Save results
    if output_path is None:
        if metadata_dir is None:
            metadata_dir = METADATA_DIR
        output_path = Path(metadata_dir) / "step5_collections.json"
    
    clusterer.save_collections(collections_data, output_path)
    
    return collections_data