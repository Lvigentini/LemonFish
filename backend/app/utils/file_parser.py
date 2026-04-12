"""
fileparsetool
支持PDF、Markdown、TXT文件的文本提取
"""

import os
from pathlib import Path
from typing import List, Optional

from .locale import t


def _read_text_with_fallback(file_path: str) -> str:
    """
    读取文本文件，UTF-8失败时自动探测编码。
    
    采用多级回退策略：
    1. 首先尝试 UTF-8 解码
    2. use charset_normalizer detectencode
    3. 回退到 chardet 检测编码
    4. finallyuse UTF-8 + errors='replace' fallback
    
    Args:
        file_path: filepath
        
    Returns:
        解码后的文本内容
    """
    data = Path(file_path).read_bytes()
    
    # 首先尝试 UTF-8
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        pass
    
    # attemptuse charset_normalizer detectencode
    encoding = None
    try:
        from charset_normalizer import from_bytes
        best = from_bytes(data).best()
        if best and best.encoding:
            encoding = best.encoding
    except Exception:
        pass
    
    # 回退到 chardet
    if not encoding:
        try:
            import chardet
            result = chardet.detect(data)
            encoding = result.get('encoding') if result else None
        except Exception:
            pass
    
    # finallyfallback: use UTF-8 + replace
    if not encoding:
        encoding = 'utf-8'
    
    return data.decode(encoding, errors='replace')


class FileParser:
    """文件解析器"""

    # Phase 7.6: added .csv for structured stakeholder input
    SUPPORTED_EXTENSIONS = {'.pdf', '.md', '.markdown', '.txt', '.csv'}

    @classmethod
    def extract_text(cls, file_path: str) -> str:
        """
        从文件中提取文本

        Args:
            file_path: filepath

        Returns:
            提取的文本内容
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(t('backend.fileNotFound', path=file_path))

        suffix = path.suffix.lower()

        if suffix not in cls.SUPPORTED_EXTENSIONS:
            raise ValueError(t('backend.unsupportedFormat', format=suffix))

        if suffix == '.pdf':
            return cls._extract_from_pdf(file_path)
        elif suffix in {'.md', '.markdown'}:
            return cls._extract_from_md(file_path)
        elif suffix == '.txt':
            return cls._extract_from_txt(file_path)
        elif suffix == '.csv':
            return cls._extract_from_csv(file_path)

        raise ValueError(t('backend.unprocessableFormat', format=suffix))
    
    @staticmethod
    def _extract_from_pdf(file_path: str) -> str:
        """从PDF提取文本"""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError(t('backend.pymupdfRequired'))
        
        text_parts = []
        with fitz.open(file_path) as doc:
            for page in doc:
                text = page.get_text()
                if text.strip():
                    text_parts.append(text)
        
        return "\n\n".join(text_parts)
    
    @staticmethod
    def _extract_from_md(file_path: str) -> str:
        """从Markdown提取文本，支持自动编码检测"""
        return _read_text_with_fallback(file_path)
    
    @staticmethod
    def _extract_from_txt(file_path: str) -> str:
        """从TXT提取文本，支持自动编码检测"""
        return _read_text_with_fallback(file_path)

    @staticmethod
    def _extract_from_csv(file_path: str) -> str:
        """Phase 7.6: extract a CSV of stakeholders into narrative text.

        The CSV is expected to have column headers that describe each row.
        Each row is rendered as a structured paragraph so the ontology
        generator sees named entities instead of a table.

        Recognised columns (case-insensitive, any subset):
            name, role, organization/organisation, description, position,
            background, sentiment, stake

        Unknown columns are appended as "key: value" pairs after the
        main description. Rows with no recognisable name column are skipped.
        """
        import csv as _csv

        raw_text = _read_text_with_fallback(file_path)
        rows = []
        # Try to sniff the delimiter
        try:
            dialect = _csv.Sniffer().sniff(raw_text[:2000], delimiters=',;\t|')
        except _csv.Error:
            dialect = _csv.excel
        reader = _csv.DictReader(raw_text.splitlines(), dialect=dialect)

        paragraphs = []
        header_line = f"=== Stakeholder CSV: {Path(file_path).name} ==="
        paragraphs.append(header_line)
        paragraphs.append(
            "The following is a structured list of stakeholders, "
            "each representing a real-world actor who can interact on social media:"
        )
        paragraphs.append("")

        # Build a name-key lookup from actual headers
        name_keys = ('name', 'stakeholder', 'actor', 'entity', 'person', 'org', 'organization', 'organisation')
        role_keys = ('role', 'title', 'position', 'profession')
        desc_keys = ('description', 'background', 'bio', 'summary', 'about')
        sentiment_keys = ('sentiment', 'stance', 'position_on', 'opinion')

        for i, row in enumerate(reader, 1):
            # Find the name
            name = None
            lower_row = {k.lower().strip(): v for k, v in row.items() if k}
            for k in name_keys:
                if k in lower_row and lower_row[k].strip():
                    name = lower_row[k].strip()
                    break
            if not name:
                continue

            role = next((lower_row[k] for k in role_keys if k in lower_row and lower_row[k].strip()), None)
            description = next((lower_row[k] for k in desc_keys if k in lower_row and lower_row[k].strip()), None)
            sentiment = next((lower_row[k] for k in sentiment_keys if k in lower_row and lower_row[k].strip()), None)

            # Build a narrative paragraph
            parts = [f"Stakeholder {i}: **{name}**"]
            if role:
                parts.append(f"({role})")
            parts.append('.')
            if description:
                parts.append(f" {description.strip()}")
            if sentiment:
                parts.append(f" Position/sentiment: {sentiment.strip()}.")

            # Append any other non-empty columns we didn't already use
            used = set(name_keys) | set(role_keys) | set(desc_keys) | set(sentiment_keys)
            extras = []
            for k, v in lower_row.items():
                if k not in used and v and v.strip():
                    extras.append(f"{k}={v.strip()}")
            if extras:
                parts.append(f" ({', '.join(extras)})")

            paragraphs.append(''.join(parts))

        if len(paragraphs) <= 3:
            # No recognisable rows — fall back to raw text
            return raw_text

        return '\n\n'.join(paragraphs)
    
    @classmethod
    def extract_from_multiple(cls, file_paths: List[str]) -> str:
        """
        从多个文件提取文本并合并
        
        Args:
            file_paths: filepathlist
            
        Returns:
            合并后的文本
        """
        all_texts = []
        
        for i, file_path in enumerate(file_paths, 1):
            try:
                text = cls.extract_text(file_path)
                filename = Path(file_path).name
                all_texts.append(f"{t('backend.documentHeader', index=i, filename=filename)}\n{text}")
            except Exception as e:
                all_texts.append(t('backend.documentExtractionFailed', index=i, path=file_path, error=str(e)))
        
        return "\n\n".join(all_texts)


def split_text_into_chunks(
    text: str, 
    chunk_size: int = 500, 
    overlap: int = 50
) -> List[str]:
    """
    将文本分割成小块
    
    Args:
        text: 原始文本
        chunk_size: 每块的字符数
        overlap: 重叠字符数
        
    Returns:
        文本块列表
    """
    if len(text) <= chunk_size:
        return [text] if text.strip() else []
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # 尝试在句子边界处分割
        if end < len(text):
            # 查找最近的句子结束符
            for sep in ['。', '！', '？', '.\n', '!\n', '?\n', '\n\n', '. ', '! ', '? ']:
                last_sep = text[start:end].rfind(sep)
                if last_sep != -1 and last_sep > chunk_size * 0.3:
                    end = start + last_sep + len(sep)
                    break
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # 下一个块从重叠位置开始
        start = end - overlap if end < len(text) else len(text)
    
    return chunks

