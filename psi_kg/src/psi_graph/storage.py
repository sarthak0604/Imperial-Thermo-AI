"""Keep original resources only when explicitly requested."""

from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from .common import file_hash, now, write_json


@contextmanager
def source_storage(output, resources, source_url, keep_originals=False):
    if keep_originals:
        yield output
        return
    # Place scratch files on the output volume (including cloud /data), not RAM /tmp.
    with TemporaryDirectory(prefix=".originals-", dir=output) as scratch:
        root = Path(scratch).resolve()
        try:
            yield root
        finally:
            for record in resources:
                local = record.get("local_path")
                if not local or not Path(local).resolve().is_relative_to(root):
                    continue  # Never delete originals retained by an earlier run.
                path = Path(local)
                try:
                    verified = (
                        path.is_file()
                        and path.stat().st_size == record.get("size_bytes")
                        and bool(record.get("sha256"))
                        and file_hash(path) == record["sha256"]
                    )
                except OSError:
                    verified = False
                record.update(
                    original_retention="discarded",
                    original_verified_before_discard=verified,
                    original_discarded_at=now(),
                    local_path=None,
                    storage_uri=None,
                )
            write_json(
                output / "resources_manifest.json",
                dict(source_url=source_url, generated_at=now(), resources=resources),
            )
    # TemporaryDirectory removes originals and archive members even on exceptions.
