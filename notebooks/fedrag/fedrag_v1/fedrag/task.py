"""fedrag: A Flower Federated RAG app."""

from typing import List

from flwr.common.typing import Parameters


def str_to_parameters(text: List[str]) -> Parameters:
    tensors = [str.encode(t) for t in text]
    return Parameters(tensors=tensors, tensor_type="string")


def parameters_to_str(parameters: Parameters) -> List[str]:
    text = [param.decode() for param in parameters.tensors]
    return text
