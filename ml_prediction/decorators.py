from functools import wraps
from rest_framework import status
from core.responses import error_response
from ml_prediction.services import ModelNotReady, active_model_version, load_model


def model_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        version = active_model_version()
        if version is None:
            return error_response("No trained model is active yet. An administrator must train the model first.", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
        try:
            load_model(version)
        except ModelNotReady as error:
            return error_response(str(error), status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

        request.model_version = version
        return view_func(request, *args, **kwargs)
    return wrapper