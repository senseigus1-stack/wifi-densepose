from pydantic import BaseModel, Field
from typing import Optional

class Config(BaseModel):
    # Network
    udp_ip: str = Field("0.0.0.0", description="UDP listen IP")
    udp_port: int = Field(5566, ge=1, le=65535, description="UDP port")
    
    # Signal processing
    sampling_rate: int = Field(100, description="Sampling rate (Hz)")
    filter_low: float = Field(0.5, description="Low cutoff (Hz)")
    filter_high: float = Field(10.0, description="High cutoff (Hz)")
    window_size: int = Field(10, description="Number of time frames")
    
    # Model
    model_id: str = Field("ruvnet/wifi-densepose-mmfi-pose", description="HuggingFace model ID")
    model_input_shape: tuple = (3, 114, 10)
    models_dir: str = Field("models", description="Directory for cached models")
    
    # Presence detection
    presence_energy_threshold: float = Field(0.15, description="Energy threshold")
    presence_timeout: float = Field(2.0, description="Timeout (seconds)")
    
    # Multi-person tracking
    max_people: int = Field(4, ge=1, le=10)
    person_id_timeout: float = Field(3.0, description="ID expiration (seconds)")
    
    # Visualization
    viz_width: int = 1024
    viz_height: int = 768
    smoothing_alpha: float = Field(0.3, ge=0.0, le=1.0, description="Smoothing factor")
    
    # Logging
    log_level: str = Field("INFO", description="Logging level")
    log_file: Optional[str] = Field(None, description="Path to log file")

config = Config()