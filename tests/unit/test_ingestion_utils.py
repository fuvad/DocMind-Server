import pytest
from src.rag.ingestion.utils import analyze_elements, get_page_number

class DummyElement:
    pass

class Table(DummyElement): pass
class Image(DummyElement): pass
class Title(DummyElement): pass
class Header(DummyElement): pass
class NarrativeText(DummyElement): pass
class Text(DummyElement): pass
class ListItem(DummyElement): pass
class FigureCaption(DummyElement): pass
class UnknownType(DummyElement): pass

def test_analyze_elements_empty():
    assert analyze_elements([]) == {
        "text": 0, "tables": 0, "images": 0, "titles": 0, "other": 0
    }

def test_analyze_elements_mixed():
    elements = [
        Table(), Image(), Title(), Header(), 
        NarrativeText(), Text(), ListItem(), FigureCaption(),
        UnknownType(), UnknownType()
    ]
    result = analyze_elements(elements)
    assert result == {
        "text": 4,     # NarrativeText, Text, ListItem, FigureCaption
        "tables": 1,
        "images": 1,
        "titles": 2,   # Title, Header
        "other": 2     # UnknownType x2
    }

class DummyChunk:
    def __init__(self, metadata=None):
        if metadata:
            self.metadata = metadata

class DummyMetadata:
    def __init__(self, page_number=None):
        if page_number is not None:
            self.page_number = page_number

def test_get_page_number_with_metadata_page():
    chunk = DummyChunk(metadata=DummyMetadata(page_number=42))
    assert get_page_number(chunk, 0) == 42

def test_get_page_number_with_metadata_but_no_page():
    chunk = DummyChunk(metadata=DummyMetadata())
    assert get_page_number(chunk, 5) == 6

def test_get_page_number_without_metadata():
    chunk = DummyChunk()
    assert get_page_number(chunk, 10) == 11
