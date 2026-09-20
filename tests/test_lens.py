from __future__ import annotations

import logging
import os
from importlib import resources

import flare
import tests
from flare.api.database import load_model


def test_lens() -> None:
    resources_dir = resources.files(flare.__name__).joinpath('resources')
    path = os.path.join(resources_dir, 'model', 'Nikon', 'ai_50_135mm.json')
    model = load_model(path)

    logging.info(model)


if __name__ == '__main__':
    tests.init()
    test_lens()
