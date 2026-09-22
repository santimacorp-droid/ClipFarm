import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base

class Campaign(Base):
    __tablename__ = "campaigns"

    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name        = Column(String, nullable=False)
    brand_name  = Column(String)
    schema_json = Column(Text, nullable=False)   # full CampaignSchema as JSON string
    status      = Column(String, default="draft")
    # status: draft | active | downloading | transcribing | finding_moments | cutting | done | failed
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    clips = relationship("CampaignClip", back_populates="campaign", cascade="all, delete-orphan")

class CampaignClip(Base):
    __tablename__ = "campaign_clips"

    id              = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id     = Column(String, ForeignKey("campaigns.id"), nullable=False)
    moment_name     = Column(String)
    clip_data_json  = Column(Text)   # full CampaignClipSchema as JSON string
    status          = Column(String, default="pending")
    created_at      = Column(DateTime, default=datetime.utcnow)

    campaign = relationship("Campaign", back_populates="clips")
