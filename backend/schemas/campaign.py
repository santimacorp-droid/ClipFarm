from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Dict, Any
from enum import Enum
import warnings

warnings.filterwarnings("ignore", message=r'.*schema_json.*', category=UserWarning)

class LogoPosition(str, Enum):
    top_right    = "top_right"
    top_left     = "top_left"
    bottom_right = "bottom_right"
    bottom_left  = "bottom_left"

class SubtitleMode(str, Enum):
    native_preferred = "native_preferred"
    styled_burned    = "styled_burned"
    clean_srt_only   = "clean_srt_only"
    optional         = "optional"
    none             = "none"
    required         = "required"

class CampaignCaptionStyle(str, Enum):
    hormozi_yellow = "hormozi_yellow"
    neon_green     = "neon_green"
    neon_cyan      = "neon_cyan"
    minimal_box    = "minimal_box"
    none           = "none"

class OutputFormat(str, Enum):
    original    = "original"    # keep source aspect ratio
    crop_center = "crop_center" # crop center column to 9:16
    blur_pad    = "blur_pad"    # blur-padded background (default)

class EditMode(str, Enum):
    moment_extraction = "moment_extraction"   # default — current behavior
    full_video_edit   = "full_video_edit"     # short video: keep whole, clean up

class OutroStyle(str, Enum):
    none          = "none"
    follow_handle = "follow_handle"   # "Follow @{handle}" + "for more"
    check_bio     = "check_bio"       # "Link in bio"
    custom_text   = "custom_text"     # user-defined text

class CTAStyle(str, Enum):
    none            = "none"
    follow_tap      = "follow_tap"      # finger tap animation (TikTok/IG/FB)
    subscribe_click = "subscribe_click" # YouTube subscribe button click
    follow_pulse    = "follow_pulse"    # pulsing glow button
    bell_shake      = "bell_shake"      # bell shake animation
    slide_up        = "slide_up"        # button slides up from bottom edge

class CTAPosition(str, Enum):
    bottom_right  = "bottom_right"
    bottom_left   = "bottom_left"
    bottom_center = "bottom_center"

class CTAPlatform(str, Enum):
    auto           = "auto"           # detect from platform_tags
    tiktok         = "tiktok"
    instagram      = "instagram"
    youtube        = "youtube"
    youtube_shorts = "youtube_shorts"
    facebook       = "facebook"

class PriorityMoment(BaseModel):
    name:        str
    description: Optional[str] = None
    start_line:  Optional[str] = None   # exact or near-exact quote to locate in transcript

class ClipDuration(BaseModel):
    min_seconds:     float = 15.0
    max_seconds:     float = 180.0
    is_moment_based: bool  = False

    @model_validator(mode="after")
    def validate_duration(self):
        # Prevent absurd / broken durations (e.g. 1s - 2s from 'Tier 1-2')
        if self.max_seconds < 10.0 or (self.min_seconds <= 2.0 and self.max_seconds <= 5.0):
            self.min_seconds = 15.0
            self.max_seconds = 90.0
            self.is_moment_based = True
        elif self.min_seconds >= self.max_seconds:
            self.max_seconds = self.min_seconds + 45.0
        return self

class PlatformTags(BaseModel):
    tiktok:         List[str] = []
    instagram:      List[str] = []
    youtube_shorts: List[str] = []
    facebook:       List[str] = []

class CampaignRestrictions(BaseModel):
    subtitles:              SubtitleMode         = SubtitleMode.native_preferred
    caption_style:          CampaignCaptionStyle = CampaignCaptionStyle.hormozi_yellow
    styled_captions:        bool  = False
    show_hook_banner:       bool  = True    # burn opening text hook headline banner
    background_music:       str   = "allowed_low"   # "allowed_low" | "not_recommended" | "forbidden"
    logo_required:          bool  = True
    logo_position:          LogoPosition = LogoPosition.top_right
    logo_scale_percent:     float = 0.12             # logo width as fraction of video width
    output_format:          OutputFormat = OutputFormat.blur_pad
    other_people_allowed:   bool  = False
    external_footage_allowed: bool = False
    filters_allowed:        bool  = False
    edit_mode:             EditMode   = EditMode.moment_extraction
    outro_style:           OutroStyle = OutroStyle.none
    outro_text:            str        = ""      # used when outro_style = custom_text
    outro_handle:          str        = ""      # e.g. "@frida"
    remove_dead_air:       bool       = True    # auto-remove silence gaps
    silence_threshold_db:  float      = -40.0   # dB below which is silence
    silence_gap_min_sec:   float      = 1.2     # gaps longer than this get trimmed
    silence_keep_sec:      float      = 0.4     # how much silence to retain
    cta_style:             CTAStyle    = CTAStyle.none
    cta_platform:          CTAPlatform = CTAPlatform.auto
    cta_position:          CTAPosition = CTAPosition.bottom_right
    cta_handle:            str         = ""    # e.g. "@frida"
    cta_start_offset:      Optional[float] = None  # seconds from start; None = last 4.5s

class CampaignCompliance(BaseModel):
    min_days_live:             int   = 30
    min_engagement_rate:       float = 0.002
    likes_must_be_visible:     bool  = True
    tier1_2_audience_required: bool  = True
    ftc_compliant:             bool  = True

class CampaignSchema(BaseModel):
    brand_name:       str = "Unknown Brand"
    campaign_name:    str = "Untitled Campaign"
    source_video_url: Optional[str] = None
    logo_url:         Optional[str] = None
    clip_duration:    ClipDuration  = Field(default_factory=ClipDuration)
    priority_moments: List[PriorityMoment] = []
    caption_options:  List[str] = []
    platform_tags:    PlatformTags = Field(default_factory=PlatformTags)
    restrictions:     CampaignRestrictions = Field(default_factory=CampaignRestrictions)
    compliance:       CampaignCompliance = Field(default_factory=CampaignCompliance)
    max_clips:        Optional[int] = None
    raw_brief:        Optional[str] = None

class CampaignCreate(BaseModel):
    raw_brief: Optional[str] = None    # user pastes raw brief text
    schema_json: Optional[dict] = None # or provides structured schema directly
    name: Optional[str] = None
    brand_name: Optional[str] = None

class CampaignUpdate(BaseModel):
    model_config = {"protected_namespaces": ()}
    schema_json: dict  # user can patch the parsed schema

class ComplianceItem(BaseModel):
    item:    str
    status:  str   # "pass" | "fail" | "manual" | "pending"
    value:   Optional[str] = None

class CampaignClipSchema(BaseModel):
    id:                   str
    campaign_id:          str
    moment_name:          str
    video_file:           Optional[str] = None
    logo_video_file:      Optional[str] = None   # logo-watermarked version
    captioned_video_file: Optional[str] = None   # burned-caption version
    cta_video_file:       Optional[str] = None   # burned-CTA overlay version
    cta_platforms:        Optional[Dict[str, str]] = None  # platform -> video path mapping
    cta_style:            Optional[str] = None
    cta_platform:         Optional[str] = None
    vertical_video_file:  Optional[str] = None
    srt_file:             Optional[str] = None
    subtitle_mode:        Optional[str] = None
    output_format:        Optional[str] = None
    duration_seconds:     Optional[float] = None
    start_sec:            Optional[float] = None
    end_sec:              Optional[float] = None
    confidence:           str = "low"  # "high" | "low"
    matched_text:         Optional[str] = None
    hook_text:            Optional[str] = None   # viral on-screen headline hook
    caption_suggestions:  List[dict] = []
    platform_post_guide:  dict = {}
    compliance_checklist: List[ComplianceItem] = []
    publish_log:          List[dict] = []
    status:               str = "pending"  # "pending" | "cutting" | "done" | "failed"

# Backward-compatibility aliases
MomentDefinition = PriorityMoment
CampaignCreateRequest = CampaignCreate
CampaignUpdateRequest = CampaignUpdate
ClipPackage = CampaignClipSchema

class CampaignResponse(BaseModel):
    id: str
    name: str
    brand_name: Optional[str] = None
    status: str
    schema_data: Optional[Dict[str, Any]] = Field(default=None, alias="schema")
    clips: List[CampaignClipSchema] = []
    created_at: Optional[str] = None
