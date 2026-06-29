import os
import sys

from .orchestrator import main

if __name__ == "__main__":
    # PaaS web entrypoint — serve the UI when invoked bare with $PORT set.
    if len(sys.argv) == 1 and os.getenv("PORT"):  # bare `python -m signalfund` on a PaaS (Render sets PORT)
        from . import webapp
        webapp.serve(host="0.0.0.0", port=int(os.getenv("PORT")), open_browser=False)
    else:
        # ...otherwise run the existing sourcing CLI unchanged.
        main()
