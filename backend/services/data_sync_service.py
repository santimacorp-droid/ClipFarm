"""
Data synchronization service - synchronize processing results to database
"""

import json
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from sqlalchemy.orm import Session
from backend.models.clip import Clip, ClipStatus
from backend.models.collection import Collection, CollectionStatus
from backend.models.project import Project, ProjectStatus, ProjectType
from backend.models.task import Task, TaskStatus, TaskType
from datetime import datetime

logger = logging.getLogger(__name__)


class DataSyncService:
    """data synchronization service"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def sync_all_projects_from_filesystem(self, data_dir: Path) -> Dict[str, Any]:
        """Synchronize all projects from filesystem to database"""
        try:
            logger.info(f"Starting synchronization of all projects from file system: {data_dir}")
            
            projects_dir = data_dir / "projects"
            if not projects_dir.exists():
                logger.warning(f"project directory does not exist: {projects_dir}")
                return {"success": False, "error": "project directory does not exist"}
            
            synced_projects = []
            failed_projects = []
            
            # iterate over all project directories
            for project_dir in projects_dir.iterdir():
                if project_dir.is_dir() and not project_dir.name.startswith('.') and project_dir.name != 'tmp':
                    project_id = project_dir.name
                    try:
                        result = self.sync_project_from_filesystem(project_id, project_dir)
                        if result["success"]:
                            synced_projects.append(project_id)
                        else:
                            failed_projects.append({"project_id": project_id, "error": result.get("error")})
                    except Exception as e:
                        logger.error(f"Synchronize project {project_id} Failure: {str(e)}")
                        failed_projects.append({"project_id": project_id, "error": str(e)})
            
            logger.info(f"Sync complete: success {len(synced_projects)} , failed {len(failed_projects)} A / An")
            
            return {
                "success": True,
                "synced_projects": synced_projects,
                "failed_projects": failed_projects,
                "total_synced": len(synced_projects),
                "total_failed": len(failed_projects)
            }
            
        except Exception as e:
            logger.error(f"Failed to synchronize all projects: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def sync_project_from_filesystem(self, project_id: str, project_dir: Path) -> Dict[str, Any]:
        """Synchronize single project from filesystem to database"""
        try:
            logger.info(f"Starting project synchronization: {project_id}")
            
            # Check if project already exists in database
            existing_project = self.db.query(Project).filter(Project.id == project_id).first()
            project_metadata = self._read_project_metadata(project_dir) or {}
            
            if existing_project:
                logger.info(f"Project {project_id} Already in database, checking metadata and continuing sync")
                if (not existing_project.name or existing_project.name.startswith("Project_")) and project_metadata.get("project_name"):
                    existing_project.name = project_metadata["project_name"]
                if not existing_project.video_path and project_metadata.get("video_path"):
                    existing_project.video_path = project_metadata["video_path"]
                if not existing_project.thumbnail and project_metadata.get("thumbnail"):
                    existing_project.thumbnail = project_metadata["thumbnail"]
                self.db.commit()
            else:
                # create project record
                project = Project(
                    id=project_id,
                    name=project_metadata.get("project_name", f"Project_{project_id[:8]}"),
                    description=project_metadata.get("description", ""),
                    project_type=ProjectType.KNOWLEDGE,  # Default Type
                    status=ProjectStatus.COMPLETED if project_metadata.get("status") == "completed" else ProjectStatus.PENDING,
                    video_path=project_metadata.get("video_path"),
                    thumbnail=project_metadata.get("thumbnail"),
                    processing_config=project_metadata.get("processing_config", {}),
                    project_metadata=project_metadata
                )
                
                self.db.add(project)
                self.db.commit()
                self.db.refresh(project)
                
                logger.info(f"Project {project_id} Successfully synchronized to database")
            
            # sync slice data
            clips_count = self._sync_clips_from_filesystem(project_id, project_dir)
            
            # sync collection data
            logger.info(f"Starting project synchronization {project_id} Set data of")
            collections_count = self._sync_collections_from_filesystem(project_id, project_dir)
            logger.info(f"Project {project_id} Collection sync complete, synchronized {collections_count} collections")
            
            # Check if project has completed processing, update project status
            self._update_project_status_if_completed(project_id, project_dir)
            
            return {
                "success": True,
                "project_id": project_id,
                "clips_synced": clips_count,
                "collections_synced": collections_count
            }
            
        except Exception as e:
            logger.error(f"Synchronize project {project_id} Failure: {str(e)}")
            self.db.rollback()
            return {"success": False, "error": str(e)}
    
    def _read_project_metadata(self, project_dir: Path) -> Optional[Dict[str, Any]]:
        """read project metadata"""
        metadata_files = [
            project_dir / "project.json",
            project_dir / "metadata.json",
            project_dir / "info.json"
        ]
        
        for metadata_file in metadata_files:
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception as e:
                    logger.warning(f"Reading metadata file failed {metadata_file}: {e}")
        
        # Fallback: recover title and category from clips_metadata.json or step1_outline.json
        candidate_name = None
        candidate_category = None
        for cand_file in [project_dir / "metadata" / "clips_metadata.json", project_dir / "metadata" / "step1_outline.json"]:
            if cand_file.exists():
                try:
                    with open(cand_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, list) and len(data) > 0:
                            candidate_name = data[0].get("outline") or data[0].get("title")
                            candidate_category = data[0].get("category")
                            if candidate_name:
                                break
                except Exception:
                    pass

        raw_video = project_dir / "raw" / "input.mp4"
        raw_cover = project_dir / "raw" / "input_cover.jpg"

        thumbnail_b64 = None
        if raw_cover.exists():
            try:
                import base64
                with open(raw_cover, "rb") as cf:
                    thumbnail_b64 = f"data:image/jpeg;base64,{base64.b64encode(cf.read()).decode('utf-8')}"
            except Exception:
                pass

        return {
            "project_name": candidate_name or f"Project_{project_dir.name[:8]}",
            "video_path": str(raw_video) if raw_video.exists() else None,
            "source_file": str(raw_video) if raw_video.exists() else None,
            "thumbnail": thumbnail_b64,
            "category": candidate_category or "default",
            "created_at": datetime.now().isoformat(),
            "status": "completed" if (project_dir / "output" / "clips").exists() else "pending"
        }
    
    def _sync_clips_from_filesystem(self, project_id: str, project_dir: Path) -> int:
        """Synchronize slice data from file system"""
        try:
            # Find slice data file
            clips_files = [
                project_dir / "step6_video" / "clips_metadata.json",  # the most complete data source
                project_dir / "step3_all_scored.json",  # Prioritize correct data source
                project_dir / "step4_title" / "step4_title.json",
                project_dir / "step4_titles.json",
                project_dir / "clips_metadata.json",
                project_dir / "metadata" / "clips_metadata.json"
            ]
            
            clips_data = None
            for clips_file in clips_files:
                logger.info(f"Checking slice file: {clips_file}")
                if clips_file.exists():
                    try:
                        with open(clips_file, 'r', encoding='utf-8') as f:
                            clips_data = json.load(f)
                        logger.info(f"Successfully read slice file: {clips_file}, Data length: {len(clips_data) if isinstance(clips_data, list) else 'not list'}")
                        break
                    except Exception as e:
                        logger.warning(f"Reading slice file failed {clips_file}: {e}")
                else:
                    logger.info(f"Slice file does not exist: {clips_file}")
            
            if not clips_data:
                logger.info(f"Project {project_id} Slice data not found")
                return 0
            
            # Ensure clips_data is a list
            if isinstance(clips_data, dict) and "clips" in clips_data:
                clips_data = clips_data["clips"]
            elif not isinstance(clips_data, list):
                logger.warning(f"Project {project_id} Incorrect slice data format")
                return 0
            
            synced_count = 0
            updated_count = 0
            for clip_data in clips_data:
                try:
                    # Check if slice already exists
                    existing_clip = self.db.query(Clip).filter(
                        Clip.project_id == project_id,
                        Clip.title == clip_data.get("generated_title", clip_data.get("title", ""))
                    ).first()
                    
                    if existing_clip:
                        # Update existing slice's video_path and tags, force using project internal output directory
                        clip_id = clip_data.get('id', str(synced_count + 1))
                        title = clip_data.get('generated_title', clip_data.get('title', clip_data.get('outline', '')))
                        
                        # Force use of standard paths within project
                        from ..core.path_utils import get_project_directory
                        from ..utils.video_processor import VideoProcessor
                        project_dir = get_project_directory(project_id)
                        project_clips_dir = project_dir / "output" / "clips"
                        project_clips_dir.mkdir(parents=True, exist_ok=True)
                        
                        # Find actual existing file first
                        actual_file = next(project_clips_dir.glob(f"{clip_id}_*.mp4"), None)
                        if actual_file:
                            project_video_path = actual_file
                        else:
                            safe_title = VideoProcessor.sanitize_filename(title)
                            project_video_path = project_clips_dir / f"{clip_id}_{safe_title}.mp4"
                        
                        # Compatible with old global output directory, migrate if exists
                        from ..core.path_utils import get_data_directory
                        legacy_video_path = get_data_directory() / "output" / "clips" / project_video_path.name
                        try:
                            if legacy_video_path.exists() and not project_video_path.exists():
                                import shutil
                                shutil.copy2(legacy_video_path, project_video_path)
                                logger.info(f"Migrating old slice files to project directory: {legacy_video_path} -> {project_video_path}")
                        except Exception as _e:
                            logger.warning(f"Migration of old slice files failed: {legacy_video_path} -> {project_video_path}: {_e}")
                        
                        # Always use project internal paths
                        video_path = str(project_video_path)
                        logger.info(f"Update slice {existing_clip.id} 'svideo_path: {video_path}")
                        existing_clip.video_path = video_path
                        existing_clip.clip_metadata = clip_data
                        if clip_data.get('tags'):
                            existing_clip.tags = clip_data.get('tags')
                        elif existing_clip.tags is None:
                            existing_clip.tags = []  # Ensure tags is an empty list instead of null
                        updated_count += 1
                        continue
                    
                    # convert time format
                    start_time = self._convert_time_to_seconds(clip_data.get('start_time', '00:00:00'))
                    end_time = self._convert_time_to_seconds(clip_data.get('end_time', '00:00:00'))
                    duration = end_time - start_time
                    
                    # Build video file path, force using project internal directory
                    clip_id = clip_data.get('id', str(synced_count + 1))
                    title = clip_data.get('generated_title', clip_data.get('title', clip_data.get('outline', '')))
                    
                    # Force use project internal paths
                    from ..core.path_utils import get_project_directory, get_data_directory
                    project_dir = get_project_directory(project_id)
                    project_clips_dir = project_dir / "output" / "clips"
                    project_clips_dir.mkdir(parents=True, exist_ok=True)
                    
                    actual_file = next(project_clips_dir.glob(f"{clip_id}_*.mp4"), None)
                    if actual_file:
                        project_video_path = actual_file
                    else:
                        from ..utils.video_processor import VideoProcessor
                        safe_title = VideoProcessor.sanitize_filename(title)
                        project_video_path = project_clips_dir / f"{clip_id}_{safe_title}.mp4"
                    
                    # Compatible with old global output directory, migrate if exists
                    global_clips_dir = get_data_directory() / "output" / "clips"
                    global_video_path = global_clips_dir / project_video_path.name
                    
                    if global_video_path.exists() and not project_video_path.exists():
                        import shutil
                        shutil.copy2(global_video_path, project_video_path)
                        logger.info(f"Moving slice file from global directorymigrate to project directory: {global_video_path} -> {project_video_path}")
                    
                    # Always use project internal paths
                    video_path = str(project_video_path)
                    
                    # Attach platform duration advisory
                    try:
                        from ..core.platform_advisor import get_platform_advisory
                        if "platform_advisory" not in clip_data:
                            clip_data["platform_advisory"] = get_platform_advisory(duration)
                    except Exception as adv_err:
                        logger.debug(f"Platform advisory calculation failed: {adv_err}")

                    clip = Clip(
                        project_id=project_id,
                        title=clip_data.get('generated_title', clip_data.get('title', clip_data.get('outline', ''))),
                        description=clip_data.get('recommend_reason', ''),
                        start_time=start_time,
                        end_time=end_time,
                        duration=duration,
                        score=clip_data.get('final_score', 0.0),
                        video_path=video_path,
                        tags=clip_data.get('tags', []),
                        clip_metadata=clip_data,
                        status=ClipStatus.COMPLETED
                    )
                    
                    self.db.add(clip)
                    synced_count += 1
                    
                except Exception as e:
                    logger.error(f"Synchronizing slice failed: {e}")
                    continue
            
            self.db.commit()
            logger.info(f"Project {project_id} Synchronized {synced_count} , updated {updated_count} A slice")
            return synced_count
            
        except Exception as e:
            logger.error(f"sync slice dataFailure: {str(e)}")
            return 0
    
    def _sync_collections_from_filesystem(self, project_id: str, project_dir: Path) -> int:
        """Synchronize collection data from file system"""
        try:
            # Build collections directory path
            collections_dir = project_dir / "output" / "collections"
            
            # Find collection data file
            collections_files = [
                project_dir / "step6_video" / "collections_metadata.json",  # the most complete data source
                project_dir / "step5_clustering" / "step5_clustering.json",
                project_dir / "metadata" / "step5_collections.json",  # Add step5_collections.json
                project_dir / "collections_metadata.json",
                project_dir / "metadata" / "collections_metadata.json"
            ]
            
            collections_data = None
            for collections_file in collections_files:
                logger.info(f"Check collection file: {collections_file}")
                if collections_file.exists():
                    try:
                        with open(collections_file, 'r', encoding='utf-8') as f:
                            collections_data = json.load(f)
                        logger.info(f"Successfully read collection file: {collections_file}, Data length: {len(collections_data) if isinstance(collections_data, list) else 'not list'}")
                        break
                    except Exception as e:
                        logger.warning(f"Reading collection file failed {collections_file}: {e}")
                else:
                    logger.info(f"Collection file does not exist: {collections_file}")
            
            if not collections_data:
                logger.info(f"Project {project_id} Collection data not found")
                return 0
            
            # Ensure collections_data is a list
            if isinstance(collections_data, dict) and "collections" in collections_data:
                collections_data = collections_data["collections"]
            elif not isinstance(collections_data, list):
                logger.warning(f"Project {project_id} Incorrect collection data format")
                return 0
            
            # read delete record file
            deleted_collections_file = project_dir / "deleted_collections.json"
            deleted_collections = set()
            if deleted_collections_file.exists():
                try:
                    with open(deleted_collections_file, 'r', encoding='utf-8') as f:
                        deleted_data = json.load(f)
                        deleted_collections = set(deleted_data.get('deleted_collection_ids', []))
                except Exception as e:
                    logger.warning(f"Failed to read delete record: {e}")
            
            synced_count = 0
            for collection_data in collections_data:
                try:
                    collection_id = collection_data.get("id", "")
                    collection_title = collection_data.get("collection_title", "")
                    
                    # Check if deleted
                    if collection_id in deleted_collections:
                        logger.info(f"Set {collection_id} Has been deleted, skipping sync")
                        continue
                    
                    # Check if collection already exists
                    existing_collection = self.db.query(Collection).filter(
                        Collection.project_id == project_id,
                        Collection.name == collection_title
                    ).first()
                    
                    if existing_collection:
                        # Collection already exists, check if association relationships need to be established
                        collection = existing_collection
                        logger.info(f"Set {collection_title} Exists already, checking associations")
                    else:
                        # create new collection
                        collection = None
                    
                    # Build collection video file path, force using project internal directory
                    # Try multiple possible filename formats
                    possible_filenames = [
                        f"{collection_id}_{collection_title}.mp4",
                        f"{collection_title}.mp4",
                        f"collection_{collection_id}.mp4"
                    ]
                    
                    from ..core.path_utils import get_project_directory, get_data_directory
                    project_dir = get_project_directory(project_id)
                    project_collections_dir = project_dir / "output" / "collections"
                    project_collections_dir.mkdir(parents=True, exist_ok=True)
                    
                    video_path = None
                    # First search in project directory
                    for filename in possible_filenames:
                        project_video_path = project_collections_dir / filename
                        if project_video_path.exists():
                            video_path = str(project_video_path)
                            break
                    
                    # If not found in project directory, attempt global directory and migrate
                    if not video_path:
                        for filename in possible_filenames:
                            legacy_video_path = get_data_directory() / "output" / "collections" / filename
                            if legacy_video_path.exists():
                                # migrate to project directory
                                project_video_path = project_collections_dir / filename
                                import shutil
                                shutil.copy2(legacy_video_path, project_video_path)
                                video_path = str(project_video_path)
                                logger.info(f"Moving collection file from global directorymigrate to project directory: {legacy_video_path} -> {project_video_path}")
                                break
                    
                    # If still not found, use project internal path (file may not have been generated yet)
                    if not video_path:
                        video_path = str(project_collections_dir / possible_filenames[0])
                    
                    # Convert clip_ids in numeric format to UUID format
                    original_clip_ids = collection_data.get('clip_ids', [])
                    uuid_clip_ids = []
                    
                    # Get mapping relationship of all slices in project (numeric ID -> UUID)
                    clips = self.db.query(Clip).filter(Clip.project_id == project_id).all()
                    clip_id_mapping = {}
                    for clip in clips:
                        # Get original ID from clip_metadata
                        if clip.clip_metadata and 'id' in clip.clip_metadata:
                            original_id = str(clip.clip_metadata['id'])
                            clip_id_mapping[original_id] = clip.id
                    
                    # Convert clip_ids
                    for original_id in original_clip_ids:
                        if str(original_id) in clip_id_mapping:
                            uuid_clip_ids.append(clip_id_mapping[str(original_id)])
                        else:
                            logger.warning(f"Slice not foundID {original_id} CorrespondingUUID")
                    
                    # build thumbnail path
                    thumbnail_filename = f"{collection_id}_{collection_title}_thumbnail.jpg"
                    thumbnail_path = collections_dir / thumbnail_filename
                    
                    # Create new collection if it does not exist
                    if not collection:
                        collection = Collection(
                            project_id=project_id,
                            name=collection_title,
                            description=collection_data.get('collection_summary', ''),
                            video_path=video_path,
                            export_path=video_path,  # Set export_path
                            thumbnail_path=str(thumbnail_path) if thumbnail_path.exists() else None,
                            collection_metadata={
                                'clip_ids': uuid_clip_ids,  # Use clip_ids in UUID format
                                'original_clip_ids': original_clip_ids,  # retain original numeric ID
                                'collection_type': 'ai_recommended',
                                'original_id': collection_id
                            },
                            status=CollectionStatus.COMPLETED
                        )
                        
                        self.db.add(collection)
                        self.db.flush()  # Ensure collection has ID
                        logger.info(f"create new collection: {collection.id}")
                    else:
                        # Update collection metadata
                        if not collection.collection_metadata:
                            collection.collection_metadata = {}
                        collection.collection_metadata.update({
                            'clip_ids': uuid_clip_ids,
                            'original_clip_ids': original_clip_ids,
                            'collection_type': 'ai_recommended',
                            'original_id': collection_id
                        })
                        collection.video_path = video_path
                        collection.export_path = video_path  # Set export_path
                        logger.info(f"Update existing set: {collection.id}")
                    
                    # Establish association between collection and clip
                    for i, clip_id in enumerate(uuid_clip_ids):
                        try:
                            # Check if slice exists
                            clip = self.db.query(Clip).filter(Clip.id == clip_id).first()
                            if clip:
                                # Check if association already exists
                                from ..models.collection import clip_collection
                                existing_relation = self.db.execute(
                                    clip_collection.select().where(
                                        clip_collection.c.clip_id == clip_id,
                                        clip_collection.c.collection_id == collection.id
                                    )
                                ).first()
                                
                                if not existing_relation:
                                    # Use join table to insert records
                                    stmt = clip_collection.insert().values(
                                        clip_id=clip_id,
                                        collection_id=collection.id,
                                        order_index=i
                                    )
                                    self.db.execute(stmt)
                                    logger.info(f"Create set {collection.id} And slices {clip_id} Associated relationship of")
                                else:
                                    logger.info(f"Set {collection.id} And slices {clip_id} already has an association relationship")
                            else:
                                logger.warning(f"Slice {clip_id} Does not exist, skipping association")
                        except Exception as e:
                            logger.error(f"Failed to establish collection-slice association: {e}")
                    
                    synced_count += 1
                    
                except Exception as e:
                    logger.error(f"Collection sync failed: {e}")
                    continue
            
            self.db.commit()
            logger.info(f"Project {project_id} Synchronized {synced_count} collections")
            return synced_count
            
        except Exception as e:
            logger.error(f"sync collection dataFailure: {str(e)}")
            return 0
    
    def sync_project_data(self, project_id: str, project_dir: Path) -> Dict[str, Any]:
        """Synchronize project data to database"""
        try:
            logger.info(f"Starting project data synchronization: {project_id}")
            
            # Synchronize clips data
            clips_count = self._sync_clips(project_id, project_dir)
            
            # Sync collections data
            collections_count = self._sync_collections(project_id, project_dir)
            
            # update project statistics
            self._update_project_stats(project_id, clips_count, collections_count)
            
            logger.info(f"Project data synchronization complete: {project_id}, clips: {clips_count}, collections: {collections_count}")
            
            return {
                "success": True,
                "clips_synced": clips_count,
                "collections_synced": collections_count
            }
            
        except Exception as e:
            logger.error(f"Project data synchronization failed: {str(e)}")
            raise
    
    def _sync_clips(self, project_id: str, project_dir: Path) -> int:
        """Synchronize clips data"""
        clips_file = project_dir / "step4_titles.json"
        if not clips_file.exists():
            logger.warning(f"ClipsFile does not exist: {clips_file}")
            return 0
        
        try:
            with open(clips_file, 'r', encoding='utf-8') as f:
                clips_data = json.load(f)
            
            clips_count = 0
            for clip_data in clips_data:
                # check if already exists
                existing_clip = self.db.query(Clip).filter(
                    Clip.project_id == project_id,
                    Clip.title == clip_data.get("generated_title")
                ).first()
                
                if existing_clip:
                    logger.info(f"ClipAlready exists, skipping: {clip_data.get('generated_title')}")
                    continue
                
                # Create new clip record
                clip = Clip(
                    project_id=project_id,
                    title=clip_data.get("generated_title", ""),
                    description=clip_data.get("outline", ""),
                    start_time=self._parse_time(clip_data.get("start_time", "00:00:00")),
                    end_time=self._parse_time(clip_data.get("end_time", "00:00:00")),
                    duration=self._calculate_duration(
                        clip_data.get("start_time", "00:00:00"),
                        clip_data.get("end_time", "00:00:00")
                    ),
                    score=clip_data.get("final_score", 0.0),
                    status=ClipStatus.COMPLETED,
                    tags=[],
                    clip_metadata={
                        "outline": clip_data.get("outline"),
                        "content": clip_data.get("content", []),
                        "recommend_reason": clip_data.get("recommend_reason"),
                        "chunk_index": clip_data.get("chunk_index"),
                        "original_id": clip_data.get("id")
                    }
                )
                
                self.db.add(clip)
                clips_count += 1
                logger.info(f"Createclip: {clip.title}")
            
            self.db.commit()
            logger.info(f"Synchronized {clips_count} A / Anclips")
            return clips_count
            
        except Exception as e:
            logger.error(f"SyncclipsFailure: {str(e)}")
            self.db.rollback()
            raise
    
    def _sync_collections(self, project_id: str, project_dir: Path) -> int:
        """Synchronize collections data to database"""
        collections_file = project_dir / "step5_collections.json"
        if not collections_file.exists():
            logger.warning(f"CollectionsFile does not exist: {collections_file}")
            return 0
        
        try:
            # Build collections directory path
            collections_dir = project_dir / "output" / "collections"
            
            with open(collections_file, 'r', encoding='utf-8') as f:
                collections_data = json.load(f)
            
            collections_count = 0
            for collection_data in collections_data:
                # check if already exists
                existing_collection = self.db.query(Collection).filter(
                    Collection.project_id == project_id,
                    Collection.name == collection_data.get("collection_title")
                ).first()
                
                if existing_collection:
                    logger.info(f"CollectionAlready exists, skipping: {collection_data.get('collection_title')}")
                    continue
                
                # build thumbnail path
                collection_id = collection_data.get("id", "")
                collection_title = collection_data.get("collection_title", "")
                thumbnail_filename = f"{collection_id}_{collection_title}_thumbnail.jpg"
                thumbnail_path = collections_dir / thumbnail_filename
                
                # Create new collection record
                collection = Collection(
                    project_id=project_id,
                    name=collection_data.get("collection_title", ""),
                    description=collection_data.get("collection_summary", ""),
                    theme="default",
                    status=CollectionStatus.COMPLETED,
                    tags=[],
                    thumbnail_path=str(thumbnail_path) if thumbnail_path.exists() else None,
                    collection_metadata={
                        "clip_ids": collection_data.get("clip_ids", []),
                        "original_id": collection_data.get("id"),
                        "collection_type": "ai_recommended"  # mark as AI recommended
                    }
                )
                
                self.db.add(collection)
                collections_count += 1
                logger.info(f"Createcollection: {collection.name}")
            
            self.db.commit()
            logger.info(f"Synchronized {collections_count} A / Ancollections")
            return collections_count
            
        except Exception as e:
            logger.error(f"SynccollectionsFailure: {str(e)}")
            self.db.rollback()
            raise
    
    def _update_project_stats(self, project_id: str, clips_count: int, collections_count: int):
        """update project statistics"""
        try:
            project = self.db.query(Project).filter(Project.id == project_id).first()
            if project:
                project.total_clips = clips_count
                project.total_collections = collections_count
                self.db.commit()
                logger.info(f"Update project statistics: clips={clips_count}, collections={collections_count}")
        except Exception as e:
            logger.error(f"Failed to update project statistics: {str(e)}")
    
    def _parse_time(self, time_str: str) -> float:
        """Parse time string to seconds"""
        try:
            if ',' in time_str:
                time_str = time_str.replace(',', '.')
            
            parts = time_str.split(':')
            if len(parts) == 3:
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = float(parts[2])
                return hours * 3600 + minutes * 60 + seconds
            else:
                return 0.0
        except Exception:
            return 0.0
    
    def _calculate_duration(self, start_time: str, end_time: str) -> float:
        """calculate duration"""
        start_seconds = self._parse_time(start_time)
        end_seconds = self._parse_time(end_time)
        return end_seconds - start_seconds

    def _convert_time_to_seconds(self, time_str: str) -> int:
        """Convert time string to seconds"""
        try:
            # Process format "00:00:00,120" or "00:00:00.120"
            time_str = time_str.replace(',', '.')
            parts = time_str.split(':')
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds_parts = parts[2].split('.')
            seconds = int(seconds_parts[0])
            milliseconds = int(seconds_parts[1]) if len(seconds_parts) > 1 else 0
            
            total_seconds = hours * 3600 + minutes * 60 + seconds + milliseconds / 1000
            return int(total_seconds)
        except Exception as e:
            logger.error(f"Time conversion failed: {time_str}, Error: {e}")
            return 0
    
    def _update_project_status_if_completed(self, project_id: str, project_dir: Path):
        """Check if project has completed processing, if so update status to completed"""
        try:
            # Check for step6_video_output.json file, which is the completion flag
            step6_output_file = project_dir / "output" / "step6_video_output.json"
            
            if step6_output_file.exists():
                # get project record
                project = self.db.query(Project).filter(Project.id == project_id).first()
                if project and project.status != ProjectStatus.COMPLETED:
                    # Read Step 6 output file to get statistics
                    try:
                        with open(step6_output_file, 'r', encoding='utf-8') as f:
                            step6_output = json.load(f)
                        
                        # Update project status and statistics
                        project.status = ProjectStatus.COMPLETED
                        project.total_clips = step6_output.get("clips_count", 0)
                        project.total_collections = step6_output.get("collections_count", 0)
                        project.completed_at = datetime.now()
                        
                        self.db.commit()
                        logger.info(f"Project {project_id} Status updated to completed, slice count: {project.total_clips}, Number of collections: {project.total_collections}")
                        
                    except Exception as e:
                        logger.error(f"Readstep6Output file failed: {e}")
                        # Mark as completed even if read fails
                        project.status = ProjectStatus.COMPLETED
                        project.completed_at = datetime.now()
                        self.db.commit()
                        logger.info(f"Project {project_id} Status updated to completed (no statistics))")
                        
        except Exception as e:
            logger.error(f"Failed to update project status: {e}")
