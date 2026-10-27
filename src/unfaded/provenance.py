"""XMP sidecar that records what was done to a restored image.

The original file is never written to. The sidecar sits next to the output and
lists every step, the model behind it and the settings used, so a restored
print can always be told apart from a scan.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from . import __version__
from .pipeline import PhotoResult

NOTICE = (
    "Restored copy. The model invented some of the pixels in the steps listed in unfaded:Steps. "
    "The original scan was not modified."
)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def describe_steps(photo: PhotoResult) -> list[dict]:
    return [s.summary() for s in photo.steps if not s.skipped]


def build_xmp(
    source: Path, output: Path, photo: PhotoResult, when: datetime | None = None, source_hash: str | None = None
) -> str:
    when = when or datetime.now(timezone.utc)
    steps = describe_steps(photo)
    digest = file_sha256(source) if source_hash is None else source_hash
    items = "\n".join(f"     <rdf:li>{escape(json.dumps(step, sort_keys=True))}</rdf:li>" for step in steps)
    invented = [s.name for s in photo.steps if not s.skipped and s.name in ("faces", "color", "repair", "upscale")]
    return f"""<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:unfaded="https://github.com/Arthur031221/Unfaded/ns/1.0/"
    xmp:CreatorTool={quoteattr(f"Unfaded {__version__}")}
    xmp:ModifyDate={quoteattr(when.strftime("%Y-%m-%dT%H:%M:%SZ"))}
    unfaded:Source={quoteattr(source.name)}
    unfaded:SourceSha256={quoteattr(digest)}
    unfaded:Output={quoteattr(output.name)}
    unfaded:ModelGenerated={quoteattr(", ".join(invented) or "none")}>
   <dc:description>
    <rdf:Alt><rdf:li xml:lang="x-default">{escape(NOTICE)}</rdf:li></rdf:Alt>
   </dc:description>
   <unfaded:Steps>
    <rdf:Seq>
{items}
    </rdf:Seq>
   </unfaded:Steps>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>
"""


def write_sidecar(source: Path, output: Path, photo: PhotoResult) -> Path:
    path = output.with_name(output.name + ".xmp")
    path.write_text(build_xmp(source, output, photo), encoding="utf-8")
    return path
