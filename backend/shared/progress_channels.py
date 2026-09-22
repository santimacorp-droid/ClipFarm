"""
Uniform progress channel naming convention
Avoiding message loss due to inconsistent channel name
"""

def project_progress_channel(project_id: str) -> str:
    """
    Generating project progress channel name
    
    Args:
        project_id: ProjectID
        
    Returns:
        Uniform channel name: progress:project:<project_id>
    """
    # Using colon separator, removing duplicate 'project_'
    return f"progress:project:{project_id}"

def task_progress_channel(task_id: str) -> str:
    """
    Generating task progress channel name
    
    Args:
        task_id: TaskID
        
    Returns:
        Uniform channel name: progress:task:<task_id>
    """
    return f"progress:task:{task_id}"

def normalize_channel(raw: str) -> str:
    """
    Standardizing channel names, uniform format
    
    Args:
        raw: Original channel name
        
    Returns:
        Normalized channel name
    """
    if not raw:
        return ""
    
    s = raw.strip()
    
    # If in project ID format, convert to project progress channel
    if s.startswith("progress:project:"):
        return s
    elif s.startswith("project_"):
        # Removing 'project_' prefix, extracting pure ID
        project_id = s[8:]  # Removing 'project_' prefix
        return project_progress_channel(project_id)
    elif s.startswith("progress:project_"):
        # Processing 'progress:project_<id>' format
        project_id = s[17:]  # Removing 'progress:project_' prefix
        return project_progress_channel(project_id)
    else:
        # Assuming pure project ID
        return project_progress_channel(s)
