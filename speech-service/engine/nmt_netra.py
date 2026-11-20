import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class NetraNMT:
    """
    Compact 77-Million Parameter Neural Machine Translation Model for Khmer <-> English.
    """

    def __init__(self, model_path: str = "models/netra-nmt-77m", device: str = "cuda"):
        self.model_path = model_path
        self.device = device
        self._model = None
        self._tokenizer = None
        logger.info("Initialized Netra-NMT engine (target device: %s)", device)

    def translate(self, text: str, source_lang: str = "km", target_lang: str = "en") -> Dict[str, Any]:
        """
        Translates text between Khmer and English.
        Raises when the model weights have not been loaded.
        """
        if not self._model or not self._tokenizer:
            raise RuntimeError(
                "Netra-NMT model weights are not loaded. "
                f"Place the model at {self.model_path} before using the speech service."
            )

        raise RuntimeError("Netra-NMT inference is not available in this deployment.")
