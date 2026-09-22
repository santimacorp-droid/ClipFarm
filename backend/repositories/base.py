"""
Base repository class
Provides generic data access operations
"""

from typing import TypeVar, Generic, Optional, List, Dict, Any, Type
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from ..models.base import BaseModel

# Define generic types
ModelType = TypeVar("ModelType", bound=BaseModel)

class BaseRepository(Generic[ModelType]):
    """
    Base repository class providing generic CRUD operations
    
    Generic[ModelType]: Generic type, ModelType must be a subclass of BaseModel
    """
    
    def __init__(self, model: Type[ModelType], db: Session):
        """
        InitializeRepository
        
        Args:
            model: Model class
            db: Database session
        """
        self.model = model
        self.db = db
    
    def create(self, auto_commit: bool = True, **kwargs) -> ModelType:
        """
        Create record
        
        Args:
            **kwargs: Model fields and values
            
        Returns:
            Created model instance
        """
        instance = self.model(**kwargs)
        self.db.add(instance)
        if auto_commit:
            self.db.commit()
        else:
            self.db.flush()
        self.db.refresh(instance)
        return instance
    
    def get_by_id(self, id: str) -> Optional[ModelType]:
        """
        Get record by ID
        
        Args:
            id: RecordID
            
        Returns:
            Model instance orNone
        """
        return self.db.query(self.model).filter(self.model.id == id).first()
    
    def get_all(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """
        Get all records
        
        Args:
            skip: Number of skipped records
            limit: Record count limit to return
            
        Returns:
            Model instance list
        """
        return self.db.query(self.model).offset(skip).limit(limit).all()
    
    def update(self, id: str, auto_commit: bool = True, **kwargs) -> Optional[ModelType]:
        """
        Update record
        
        Args:
            id: RecordID
            **kwargs: Fields and values to update
            
        Returns:
            Updated model instance orNone
        """
        instance = self.get_by_id(id)
        if instance:
            for field, value in kwargs.items():
                if hasattr(instance, field):
                    setattr(instance, field, value)
            if auto_commit:
                self.db.commit()
            else:
                self.db.flush()
            self.db.refresh(instance)
        return instance
    
    def delete(self, id: str, auto_commit: bool = True) -> bool:
        """
        Delete record
        
        Args:
            id: RecordID
            
        Returns:
            Whether deletion was successful
        """
        instance = self.get_by_id(id)
        if instance:
            self.db.delete(instance)
            if auto_commit:
                self.db.commit()
            else:
                self.db.flush()
            return True
        return False
    
    def count(self) -> int:
        """
        Get total number of records
        
        Returns:
            Total number of records
        """
        return self.db.query(self.model).count()
    
    def exists(self, id: str) -> bool:
        """
        Check if record exists
        
        Args:
            id: RecordID
            
        Returns:
            Existence check
        """
        return self.db.query(self.model).filter(self.model.id == id).first() is not None
    
    def find_by(self, **kwargs) -> List[ModelType]:
        """
        Find records matching criteria
        
        Args:
            **kwargs: Query conditions
            
        Returns:
            List of matched model instances
        """
        filters = []
        for field, value in kwargs.items():
            if hasattr(self.model, field):
                filters.append(getattr(self.model, field) == value)
        
        if filters:
            return self.db.query(self.model).filter(and_(*filters)).all()
        return []
    
    def find_one_by(self, **kwargs) -> Optional[ModelType]:
        """
        Find a single record matching custom criteria
        
        Args:
            **kwargs: Query conditions
            
        Returns:
            Matched model instance orNone
        """
        filters = []
        for field, value in kwargs.items():
            if hasattr(self.model, field):
                filters.append(getattr(self.model, field) == value)
        
        if filters:
            return self.db.query(self.model).filter(and_(*filters)).first()
        return None
    
    def find_by_condition(self, condition) -> List[ModelType]:
        """
        Find records based on custom conditions
        
        Args:
            condition: SQLAlchemyQuery conditions
            
        Returns:
            List of matched model instances
        """
        return self.db.query(self.model).filter(condition).all()
    
    def find_one_by_condition(self, condition) -> Optional[ModelType]:
        """
        Find a single record based on custom conditions
        
        Args:
            condition: SQLAlchemyQuery conditions
            
        Returns:
            Matched model instance orNone
        """
        return self.db.query(self.model).filter(condition).first()
    
    def bulk_create(self, instances: List[Dict[str, Any]], auto_commit: bool = True) -> List[ModelType]:
        """
        Batch create records
        
        Args:
            instances: List of data dictionaries for instances to create
            
        Returns:
            List of created model instances
        """
        created_instances = []
        for instance_data in instances:
            instance = self.model(**instance_data)
            self.db.add(instance)
            created_instances.append(instance)
        
        if auto_commit:
            self.db.commit()
        else:
            self.db.flush()
        
        # Refresh all instances
        for instance in created_instances:
            self.db.refresh(instance)
        
        return created_instances
    
    def bulk_update(self, instances: List[ModelType], auto_commit: bool = True) -> List[ModelType]:
        """
        Batch update records
        
        Args:
            instances: List of instances to update
            
        Returns:
            List of updated model instances
        """
        for instance in instances:
            self.db.merge(instance)
        
        if auto_commit:
            self.db.commit()
        else:
            self.db.flush()
        return instances
    
    def bulk_delete(self, ids: List[str], auto_commit: bool = True) -> int:
        """
        Batch delete records
        
        Args:
            ids: List of IDs of records to delete
            
        Returns:
            Number of deleted records
        """
        deleted_count = self.db.query(self.model).filter(
            self.model.id.in_(ids)
        ).delete(synchronize_session=False)
        
        if auto_commit:
            self.db.commit()
        else:
            self.db.flush()
        return deleted_count