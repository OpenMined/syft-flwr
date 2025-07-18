import torch.nn as nn

from typing import List, Tuple


def init_weights(m):
    if isinstance(m, nn.Linear):
        m.weight.data.fill_(0.01)
        m.bias.data.fill_(0.01)


class SimpleMLP(nn.Module):
    def __init__(self,
                 input_shape: Tuple[int],
                 hiddens: List[int],
                 output_dim: int,
                 activation_fn=nn.ReLU):
        super().__init__()

        layers = []
        layers.append(nn.Linear(input_shape[0], output_dim))
        # layers += [nn.Linear(input_shape[0], hiddens[0]), activation_fn()]

        # for i in range(len(hiddens) - 1):
        #     layers += [nn.Linear(hiddens[i], hiddens[i + 1]), activation_fn()]

        # layers += [nn.Linear(hiddens[-1], output_dim)]

        self.body = nn.Sequential(*layers)

    def forward(self, x):
        return self.body(x)
