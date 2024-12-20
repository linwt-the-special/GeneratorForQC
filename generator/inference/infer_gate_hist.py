# AUTOGENERATED! DO NOT EDIT! File to edit: ../../src/inference/infer_gate_hist.ipynb.

# %% auto 0
__all__ = ['get_tensor_gate_length', 'get_circuit_gate_length']

# %% ../../src/inference/infer_gate_hist.ipynb 2
from ..imports import *

# %% ../../src/inference/infer_gate_hist.ipynb 4
def get_tensor_gate_length(clr_tensor, padding_token=0):
    '''Careful with padding tokens!'''
    assert clr_tensor.dim() == 3 #[b, s, t]
    
    collabsed_clr_tensor = (clr_tensor != padding_token).to(torch.int8)
    red_clr_tensor = torch.sum(collabsed_clr_tensor, dim=1)  # [b, t]
    return torch.count_nonzero(red_clr_tensor, dim=1)    # [b]

# %% ../../src/inference/infer_gate_hist.ipynb 5
def get_circuit_gate_length(qcs): 
    lengths = torch.zeros(len(qcs), dtype=int)    
    for i,qc in enumerate(qcs):         
        if hasattr(qc, "gates"):   
            lengths[i] = len(qc.gates) 
    return lengths
