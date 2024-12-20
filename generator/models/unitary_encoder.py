# AUTOGENERATED! DO NOT EDIT! File to edit: ../../src/models/unitary_encoder.ipynb.

# %% auto 0
__all__ = ['Unitary_encoder_config', 'Unitary_encoder']

# %% ../../src/models/unitary_encoder.ipynb 2
from ..imports import *
from .config_model import Config_Model
import generator.models.layers as layers
import generator.models.transformers as transformers

# %% ../../src/models/unitary_encoder.ipynb 4
@dataclass
class Unitary_encoder_config:  
    cond_emb_size: int
    model_features: list[int] 
    num_heads: int
    transformer_depths: list[int]
    dropout: float

# %% ../../src/models/unitary_encoder.ipynb 5
class Unitary_encoder(Config_Model):
    """Encoder for unitary conditions."""
    def __init__(self, cond_emb_size, model_features=None, num_heads=8, transformer_depths=[4, 4], dropout=0.1):
        super().__init__()             

        self.cond_emb_size = cond_emb_size
        
        if not exists(model_features):
            in_ch   = 2                  # complex splitted in real and img  
            mid_ch1 = cond_emb_size//4
            mid_ch2 = cond_emb_size//2
            out_ch  = cond_emb_size
            
            model_features = [in_ch, mid_ch1, mid_ch2, out_ch]

        else:
            assert len(model_features) == 4
            in_ch, mid_ch1, mid_ch2, out_ch = model_features
    
        #------------------------------------
        
        self.params_config = Unitary_encoder_config(cond_emb_size, model_features, num_heads, transformer_depths, dropout)

        #------------------------------------
          
        self.conv_in = nn.Conv2d(in_ch, mid_ch1, kernel_size=1, stride=1, padding ="same")
        self.pos_enc = layers.PositionalEncoding2D(d_model=mid_ch1) 

        self.down1 = layers.DownBlock2D(mid_ch1, mid_ch2, kernel_size=(2, 2), stride=(2, 2), padding=(0,0))    

        #------------
        assert len(transformer_depths) == 2        
        self.spatialTransformer1 = transformers.SpatialTransformerSelfAttn(mid_ch1, num_heads=num_heads, depth=transformer_depths[0], dropout=dropout)
        self.spatialTransformer2 = transformers.SpatialTransformerSelfAttn(mid_ch2, num_heads=num_heads, depth=transformer_depths[1], dropout=dropout)

        #------------
        self.head = nn.Conv2d(mid_ch2, out_ch, kernel_size=1, stride=1, padding ="same")    

        #------------------------------------
        
        self._init_weights()
    
    def _init_weights(self):
        self.head.weight.data.zero_()
    
    def forward(self, x): 
        # x ... [batch, 2, 2^n, 2^n]     n=num_of_qubits
        
        b, *_ = x.shape
        
        x = self.conv_in(x)
        x = self.pos_enc(x)     
        
        x = self.spatialTransformer1(x)
        x = self.down1(x)
                
        x = self.spatialTransformer2(x)
        
        #-------------------
        x = self.head(x)
        x = torch.reshape(x, (b, self.cond_emb_size, -1)) # [batch, ch, x, y] to  [batch, ch, seq]
        x = torch.permute(x, (0, 2, 1))                   # [batch, ch, seq]  to [batch, seq, ch]
              
        return x  
