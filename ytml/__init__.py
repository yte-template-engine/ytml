from dataclasses import dataclass
import os
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse
from xml.etree import ElementTree

import requests
from yte import process_yaml
from markdown import markdown
import plac


@dataclass
class NodeProcessor:
    base_dir: Path
    target_dir: Path
    config: Optional[Dict] = None
    config_dir: Optional[Path] = None

    def process_file(self, path: Path, toplevel: bool = True):
        if path.suffixes != [".ytml", ".yaml"] and path.suffix != [".yhtml", ".yml"]:
            raise ValueError("expected .ytml.yaml or .ytml.yml as suffix")
        with open(self.base_dir / path, "r") as f:
            code = f.read()
        html = self.process_code(code, toplevel=toplevel)
        target_path = (
            self.target_dir
            / path.parent
            / Path(Path(path.stem).stem).with_suffix(".html")
        )
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w") as f:
            f.write(html)

    def process_code(self, code, toplevel: bool = True):
        root = process_yaml(
            code,
            require_use_yte=True,
            variables={"config": self.config, "config_dir": self.config_dir},
        )
        processed = self._process_node(root)
        html = "".join(processed)
        if toplevel:
            return f"<!DOCTYPE html>{html}"
        else:
            return html

    def _process_node(self, node):
        if "html" in node and len(node) > 1:
            raise ValueError("html node may not have any siblings")

        if isinstance(node, list):
            yield "".join(
                subitem for item in node for subitem in self._process_node(item)
            )
        elif isinstance(node, dict):
            for tag, value in node.items():
                if tag == "markdown":
                    yield markdown(value)
                elif tag == "file":
                    yield self._render_file(value)
                elif tag == "include":
                    path = self.base_dir / value
                    yield from self.process_file(path, toplevel=False)
                else:
                    tag_items = [tag]
                    if isinstance(value, dict) and "content" in value:
                        content = value["content"]
                        tag_items.extend(self._render_attributes(value))
                    else:
                        content = value
                    if content is not None:
                        rendered_content = "".join(self._process_node(content))
                        yield f"<{' '.join(tag_items)}>{rendered_content}</{tag}>"
                    elif tag in ["br", "hr", "img", "input", "meta", "link"]:
                        yield f"<{' '.join(tag_items)} />"
                    else:
                        yield f"<{' '.join(tag_items)}></{tag}>"

        elif isinstance(node, str):
            yield node
        else:
            raise ValueError(f"unknown node type: {type(node)}")

    def _render_file(self, node_value):
        if "url" in node_value:
            url = node_value["url"]
            parsed = urlparse(url)
            content = requests.get(url).content
            path = os.path.basename(parsed.path)
        else:
            src_path = node_value["path"]
            if not os.path.isabs(src_path):
                src_path = self.base_dir / src_path
            with open(src_path, "rb") as f:
                content = f.read()
            path = node_value["path"]

        if node_value.get("inline"):
            if path.endswith(".svg"):
                doc = ElementTree.fromstring(content.decode())
                ns = doc.tag.split("}")[0].lstrip("{")
                ElementTree.register_namespace("", ns)
                if "class" in node_value:
                    doc.attrib["class"] = node_value["class"]
                ElementTree.register_namespace("", ns)
                content = ElementTree.tostring(doc).decode()
                return content
            else:
                raise ValueError("inline: true is only supported for SVG files")
        elif "class" in node_value:
            raise ValueError(
                "class is only supported for inline SVG files (inline: true)"
            )
        else:
            target_path = self.target_dir / path
            with open(target_path, "wb") as f:
                f.write(content)
            return path

    def _render_attributes(self, node_value):
        for key, value in node_value.items():
            if key == "content":
                continue
            if isinstance(value, list):
                if all(isinstance(item, str) for item in value):
                    value = " ".join(value)
                else:
                    raise ValueError(f"Invalid attribute: {value}")
            elif isinstance(value, dict):
                if "file" in value and len(value) == 1:
                    value = self._render_file(value["file"])
                else:
                    raise ValueError(f"Invalid attribute: {value}")
            yield f'{key}="{value}"'


@plac.pos(
    "base_dir",
    help="Base directory to which all given paths are considered to be relative.",
)
@plac.pos("target_dir", help="Target directory to which all files will be written")
@plac.pos(
    "config",
    help="Path to a .yaml file that will be used to template the processing with YTE.",
)
@plac.pos(
    "paths",
    help="Paths of .yhtml.yaml files to process, relative to base-dir.",
)
def cli(
    base_dir,
    target_dir,
    config,
    *paths,
):
    """Process .ytml.yaml files into .html files."""
    base_dir = Path(base_dir)
    target_dir = Path(target_dir)
    config_dir = None
    if config is not None:
        config_dir = Path(config).parent
        with open(config, "r") as f:
            config = process_yaml(f, require_use_yte=True)
    processor = NodeProcessor(
        base_dir, target_dir, config=config, config_dir=config_dir
    )
    for path in paths:
        processor.process_file(Path(path))


def main():
    plac.call(cli)
