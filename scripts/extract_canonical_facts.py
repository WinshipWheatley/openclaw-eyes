
import hashlib
import re

def extract_markdown_sections(markdown_text: str, source_file: str, source_commit: str) -> list[dict]:
    """
    Pure function to extract sections from Markdown text.
    Split by '##', using the first '#' as a title context if available.
    """
    sections = []
    
    # Simple regex to split by ## headers
    # Assumes sections start with ##
    parts = re.split(r'(^##\s+.*$)', markdown_text, flags=re.MULTILINE)
    
    current_title = None
    # Check for top-level title
    title_match = re.search(r'^#\s+(.*)$', markdown_text, flags=re.MULTILINE)
    if title_match:
        current_title = title_match.group(1)

    # parts[0] is everything before first ##
    # parts[1::2] are headers, parts[2::2] are bodies
    for i in range(1, len(parts), 2):
        header = parts[i].strip().replace('## ', '')
        body = parts[i+1].strip()
        
        if not body:
            continue
            
        fact_text = f"{header if not current_title else f'{current_title} > {header}'}\n\n{body}"
        content_hash = hashlib.sha256(fact_text.encode("utf-8")).hexdigest()
        
        sections.append({
            "source_file": source_file,
            "source_commit": source_commit,
            "section_heading": header,
            "fact_text": fact_text,
            "content_hash": content_hash,
            "sensitivity_class": "operational_canonical",
            "allowed_actors": ["cassandra", "chief", "guardian", "hermes"]
        })
        
    return sections
