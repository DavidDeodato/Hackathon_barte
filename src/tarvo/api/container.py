"""Linux container launcher: initialize only the fixed volume root, then drop UID.

Mount inputs/context read-only. This does not recursively change ownership or
modify source/credential directories. Existing volume contents must already be
readable/writable by the service UID; startup otherwise fails visibly.
"""
import os
from pathlib import Path
import tempfile


def main():
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        volume = Path("/data")
        if volume.is_symlink() or volume.resolve() != Path("/data"):
            raise RuntimeError("Refusing unexpected volume root")
        volume.mkdir(exist_ok=True)
        os.chown(volume, 10001, 10001)
        os.setgroups([])
        os.setgid(10001)
        os.setuid(10001)
    # Verify the mounted volume after dropping privileges, without leaving a
    # probe file or recording environment values. Health only starts afterwards.
    with tempfile.TemporaryFile(dir="/data") as probe:
        probe.write(b"tarvo-volume-probe")
        probe.flush()
        probe.seek(0)
        if probe.read() != b"tarvo-volume-probe":
            raise RuntimeError("Volume read/write probe failed")
    print("tarvo_container uid=" + str(os.geteuid()) + " volume_read_write=ok", flush=True)
    import uvicorn
    uvicorn.run("tarvo.api.main:create_app", factory=True, host="0.0.0.0",
                port=int(os.environ.get("PORT", "8000")), workers=1, proxy_headers=False)


if __name__ == "__main__":
    main()
