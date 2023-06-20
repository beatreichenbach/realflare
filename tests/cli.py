import os
import sys

from realflare.__main__ import main

if __name__ == '__main__':
    root = os.path.dirname(__file__)
    sys.argv.extend(['--project', os.path.join(root, 'project.json')])
    sys.argv.extend(['--animation', os.path.join(root, 'animation.json')])
    sys.argv.extend(['--frame-start', '0'])
    sys.argv.extend(['--frame-end', '3'])
    # sys.argv.extend(['--log', '0'])
    main()
