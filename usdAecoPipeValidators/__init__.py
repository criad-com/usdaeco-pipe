"""Five Python UsdValidation tasks over the published pipe callbacks."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from pxr import UsdValidation
from usdaeco_pipe import validators as legacy
from usdaeco_check.validation import wrap_legacy
from . import validatorTokens as tokens


def canonical(callback):
    def task(target):
        return [UsdValidation.ValidationError(e.GetName()[0].upper() + e.GetName()[1:],
                e.GetType(), e.GetSites(), e.GetMessage()) for e in callback(target, None)]
    return task


registry = UsdValidation.ValidationRegistry()
registry.RegisterPluginPrimValidator(tokens.PIPEKINDMISMATCH_CHECKER,
    wrap_legacy(tokens.PIPEKINDMISMATCH_CHECKER, canonical(legacy._kind)))
registry.RegisterPluginPrimValidator(tokens.PIPEMISSINGAXIS_CHECKER,
    wrap_legacy(tokens.PIPEMISSINGAXIS_CHECKER, canonical(legacy._axis)))
registry.RegisterPluginPrimValidator(tokens.PIPESIZENOTINTABLE_CHECKER,
    wrap_legacy(tokens.PIPESIZENOTINTABLE_CHECKER, canonical(legacy._size)))
registry.RegisterPluginStageValidator(tokens.PIPEPORTSIZEMISMATCH_CHECKER,
    wrap_legacy(tokens.PIPEPORTSIZEMISMATCH_CHECKER, canonical(legacy._port_sizes)))
registry.RegisterPluginStageValidator(tokens.PIPEGAP_CHECKER,
    wrap_legacy(tokens.PIPEGAP_CHECKER, canonical(legacy._gaps)))
