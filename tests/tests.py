from pathlib import Path
from ytml import NodeProcessor


def test_process_1():
    code = """
    html:
        head:
            title: Hello, World!
        body:
            h1: 
                content: Hello, World!
                class: head
            p: This is a test.
    """
    html = NodeProcessor(Path("foo"), Path("bar")).process_code(code)
    assert html == '<!DOCTYPE html><html><head><title>Hello, World!</title></head><body><h1 class="head">Hello, World!</h1><p>This is a test.</p></body></html>'