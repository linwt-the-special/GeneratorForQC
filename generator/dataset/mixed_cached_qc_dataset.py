# AUTOGENERATED! DO NOT EDIT! File to edit: ../../src/dataset/mixed_cached_qc_dataset.ipynb.

# %% auto 0
__all__ = ['Mixed_Cached_OpenClip_Dataset_config', 'Mixed_Cached_OpenClip_Dataset']

# %% ../../src/dataset/mixed_cached_qc_dataset.ipynb 3
from ..imports import *
from .qc_dataset import Qc_Config_Dataset_config, Qc_Config_Dataset
from .config_dataset import Config_Dataset
from .cached_qc_dataset import Cached_OpenClip_Dataset
from ..config_loader import *
from .dataset_helper import *
from ..util import DataLoaders
import dataclasses

# %% ../../src/dataset/mixed_cached_qc_dataset.ipynb 4
@dataclass
class Mixed_Cached_OpenClip_Dataset_config(Qc_Config_Dataset_config):
    pad_constant: int
    collate_fn: str
    bucket_batch_size: int
    num_down_scales: int  # for flex pad attn mask

# %% ../../src/dataset/mixed_cached_qc_dataset.ipynb 5
class Mixed_Cached_OpenClip_Dataset(Cached_OpenClip_Dataset):  
    """Dataset that uses multiple cached dataset and combines them with padding, either i) Bucket or  ii) Max. Also provides a corresponding `collate_fn` for training."""
    
    req_params = [f.name for f in dataclasses.fields(Mixed_Cached_OpenClip_Dataset_config)]
     
    cut_multiple = 4  #needed for proper downscaling!
    
    @property
    def params_config(self):
        params_config = {}
        for p in self.req_params: params_config[p] = getattr(self, p)   
        params_config["gate_pool"] = [class_to_str(gate) for gate in params_config["gate_pool"]]
        params_config = Mixed_Cached_OpenClip_Dataset_config(**params_config)
        return params_config  
        
    #-----------------------------------
    # CAUSAL ATTENTION PADDING

    def flexPadAttn_padding_collate_fn(self, b):  
        """this function is called for training for every batch"""
        z_0 = max(x[2][0] for x in b)  # space
        z_1 = max(x[2][1] for x in b)  # time
        
        #round time to next multiple of 8 for conv layers!
        z_1 = (torch.ceil(z_1 / self.cut_multiple) * self.cut_multiple).to(torch.int32)
              
        #---------------
        # key_padding_mask ... [N, S]    -inf where we want no attention
        # we will create here [N, s, t] and then reshaping is easy
        # note this is key pad mask not directly attention mask! we need this for loss masking
        # Nb: add rnd to the padding, so we train with pad and on smaller systems
        
        #we need 3 different ones for the different unet layers        
        key_padding_mask = torch.zeros((len(b), z_0, z_1), device=self.device)  
              
        padd_rnds = torch.randint(low=0, high=2, size=(len(b),2), dtype=torch.int32)    #roll 50/50 if we allow padding
                 
        xs=[]
        ys=[]
        for i,((x,y,z), padd_rnd) in enumerate(zip(b, padd_rnds)):
        # for i,(x,y,z) in enumerate(b):
            x = x[:z_0, :z_1]  # cut down to max [bits, time] of batch
            
            #-------------------  
            space, time = z[0], z[1]
        
            if space < z_0 and padd_rnd[0]: space = torch.randint(low=space, high=z_0+1, size=(1,), dtype=torch.int32)             
            if time  < z_1 and padd_rnd[1]: time  = torch.randint(low=time , high=z_1+1, size=(1,), dtype=torch.int32)                  
            
            time = (torch.ceil(time / self.cut_multiple) * self.cut_multiple).to(torch.int32)
            
            key_padding_mask[i, space:,     :] = float('-inf') 
            key_padding_mask[i,      :, time:] = float('-inf')     
            
            #-------------------   
            
            xs.append(x)
            ys.append(y)
               
        key_padding_mask_list = [key_padding_mask]
        for j in range(1, self.num_down_scales):
            key_padding_mask_list.append(F.max_pool1d(key_padding_mask_list[j-1], kernel_size=2))   
                     
        xs=torch.stack(xs)
        ys=torch.stack(ys)  
        return xs, ys, key_padding_mask_list            
   
    def flexPadAttn_TimeOnly_padding_collate_fn(self, b):  
        """this function is called for training for every batch"""
        z_0 = max(x[2][0] for x in b)  # space
        z_1 = max(x[2][1] for x in b)  # time
        
        #round time to next multiple of 8 for conv layers!
        z_1 = (torch.ceil(z_1 / self.cut_multiple) * self.cut_multiple).to(torch.int32)
              
        #---------------
        # key_padding_mask ... [N, S]    -inf where we want no attention
        # we will create here [N, s, t] and then reshaping is easy
        # note this is key pad mask not directly attention mask! we need this for loss masking
        # Nb: add rnd to the padding, so we train with pad and on smaller systems
        
        #we need 3 different ones for the different unet layers        
        key_padding_mask = torch.zeros((len(b), z_0, z_1), device=self.device)  
              
        padd_rnds = torch.randint(low=0, high=2, size=(len(b)), dtype=torch.int32)    #roll 50/50 if we allow padding
                 
        xs=[]
        ys=[]
        for i,((x,y,z), padd_rnd) in enumerate(zip(b, padd_rnds)):
        # for i,(x,y,z) in enumerate(b):
            x = x[:z_0, :z_1]  # cut down to max [bits, time] of batch
            
            #-------------------  
            time = z[1]
               
            if time  < z_1 and padd_rnd: time  = torch.randint(low=time , high=z_1+1, size=(1,), dtype=torch.int32)                       
            time = (torch.ceil(time / self.cut_multiple) * self.cut_multiple).to(torch.int32)            
            key_padding_mask[i, :, time:] = float('-inf')     
            
            #-------------------   
            
            xs.append(x)
            ys.append(y)
               
        key_padding_mask_list = [key_padding_mask]
        for j in range(1, self.num_down_scales):
            key_padding_mask_list.append(F.max_pool1d(key_padding_mask_list[j-1], kernel_size=2))   
                     
        xs=torch.stack(xs)
        ys=torch.stack(ys)  
        return xs, ys, key_padding_mask_list            

    #-----------------------------------
    # BUCKET PADDING, all x,y are already passed as batch
        
    def cut_padding_Bucket_collate_fn(self, b):     
        """this function is called for training for every batch"""    
        
        b = b[0]
        
        x = b[0]
        y = b[1]
        z = b[2]
                
        #---------------
        
        z_0 = torch.max(z[:, 0]) # space
        z_1 = torch.max(z[:, 1]) # time
                   
        #round time to next multiple of cut_multiple for conv layers!
        z_1 = (torch.ceil(z_1 / self.cut_multiple) * self.cut_multiple).to(torch.int32)
              
        #---------------      
        
        x = x[:, :z_0, :z_1]  # cut down to max [b, bits, time] of batch
        
        return x, y

    def cut_padding_Bucket_collate_fn_compilation(self, b):     
        """this function is called for training for every batch"""    
        
        b = b[0]
        
        x = b[0]
        y = b[1]                
        U = b[2]
        z = b[3]
        
        #---------------
        
        z_0 = torch.max(z[:, 0]) # space
        z_1 = torch.max(z[:, 1]) # time
                   
        #round time to next multiple of cut_multiple for conv layers!
        z_1 = (torch.ceil(z_1 / self.cut_multiple) * self.cut_multiple).to(torch.int32)
              
        #---------------      
        
        x = x[:, :z_0, :z_1]  # cut down to max [b, bits, time] of batch
        
        bit_exp = 2**z_0
        U = U[:, :, :bit_exp, :bit_exp]   # [b, Re/Im, 2^n, 2^n]
               
        return x, y, U

    def cut_padding_Bucket_collate_fn_compilation_params(self, b):     
        """this function is called for training for every batch, order in b is store dict"""    
        
        b = b[0] # {'x': 'tensor', 'y': 'numpy', 'params': 'tensor', 'U': 'tensor', 'z': 'tensor'}
        
        x = b[0]
        y = b[1]  
        p = b[2]
        U = b[3]
        z = b[4]
        
        #---------------
        
        z_0 = torch.max(z[:, 0]) # space
        z_1 = torch.max(z[:, 1]) # time
                   
        #round time to next multiple of cut_multiple for conv layers!
        z_1 = (torch.ceil(z_1 / self.cut_multiple) * self.cut_multiple).to(torch.int32)
              
        #---------------      
        
        x = x[:, :z_0, :z_1]  # cut down to max [b, bits, time] of batch

        p = p[:, :, :z_1]
        
        bit_exp = 2**z_0
        U = U[:, :, :bit_exp, :bit_exp]   # [b, Re/Im, 2^n, 2^n]
               
        return x, y, p, U
    
    #-----------------------------------
    # MAX PADDING, x are passes as sampled list (batch), std collate them
    
    def cut_padding_collate_fn(self, b):     
        """this function is called for training for every batch"""    
        z_0 = max(x[2][0] for x in b)  # space
        z_1 = max(x[2][1] for x in b)  # time
        
        #round time to next multiple of cut_multiple for conv layers!
        z_1 = (torch.ceil(z_1 / self.cut_multiple) * self.cut_multiple).to(torch.int32)
              
        #---------------      

        x_sample = b[0][0]
        xs       = torch.zeros((len(b), z_0, z_1), dtype=x_sample.dtype, device=x_sample.device)
        
        # xs=[]
        ys=[]
        for i,(x,y,z) in enumerate(b):
            #x = x[:z_0, :z_1]  # cut down to max [bits, time] of batch
            xs[i] = x[:z_0, :z_1]
            
            #xs.append(x)
            ys.append(y)
                
        #xs=torch.stack(xs)
        ys=torch.stack(ys)  
         
        return xs, ys   

    def cut_padding_collate_fn_compilation(self, b):
        """this function is called for training for every batch"""    
        z_0 = max(x[3][0] for x in b)  # space
        z_1 = max(x[3][1] for x in b)  # time
        
        #round time to next multiple of cut_multiple for conv layers!
        z_1 = (torch.ceil(z_1 / self.cut_multiple) * self.cut_multiple).to(torch.int32)

        bit_exp = 2**z_0
        
        #---------------      

        x_sample = b[0][0]
        xs       = torch.zeros((len(b), z_0, z_1), dtype=x_sample.dtype, device=x_sample.device)

        y_sample = b[0][1]
        ys       = torch.zeros((len(b), *y_sample.shape), dtype=y_sample.dtype, device=y_sample.device)

        U_sample = b[0][2]
        Us       = torch.zeros((len(b), 2, bit_exp, bit_exp), dtype=U_sample.dtype, device=U_sample.device)
        
        for i,(x,y,U,z) in enumerate(b):
            xs[i] = x[:z_0, :z_1]
            ys[i] = y
            Us[i] = U[:, :bit_exp, :bit_exp]
         
        return xs, ys, Us   

    def cut_padding_collate_fn_compilation_params(self, b):
        """this function is called for training for every batch, order in b is store dict"""    
        # {'x': 'tensor', 'y': 'numpy', 'params': 'tensor', 'U': 'tensor', 'z': 'tensor'}
        
        z_0 = max(x[4][0] for x in b)  # space
        z_1 = max(x[4][1] for x in b)  # time
        
        #round time to next multiple of cut_multiple for conv layers!
        z_1 = (torch.ceil(z_1 / self.cut_multiple) * self.cut_multiple).to(torch.int32)

        bit_exp = 2**z_0
        
        #---------------      

        x_sample = b[0][0]
        xs       = torch.zeros((len(b), z_0, z_1), dtype=x_sample.dtype, device=x_sample.device)

        y_sample = b[0][1]
        ys       = torch.zeros((len(b), *y_sample.shape), dtype=y_sample.dtype, device=y_sample.device)

        p_sample = b[0][2]
        ps       = torch.zeros((len(b), p_sample.shape[-2], z_1), dtype=p_sample.dtype, device=p_sample.device)
        
        U_sample = b[0][3]
        Us       = torch.zeros((len(b), 2, bit_exp, bit_exp), dtype=U_sample.dtype, device=U_sample.device)
        
        for i,(x,y,p,U,z) in enumerate(b):
            xs[i] = x[:z_0, :z_1]
            ys[i] = y
            ps[i] = p[:, :z_1]
            Us[i] = U[:, :bit_exp, :bit_exp]
         
        return xs, ys, ps, Us   
    
    #-----------------------------------

    def get_dataloaders(self, batch_size, text_encoder, p_valid=0.1, y_on_cpu=False):
        self.text_encoder = text_encoder
        
        excepts = []
        if y_on_cpu: excepts.append("y")
        if self.params_config.dataset_to_gpu: self.to("cuda", excepts=excepts)
        
        x_proc, y_proc, *z_proc = Qc_Config_Dataset.x_y_preprocess(self, balance_max=None, shuffle=False)    # ... z_proc is `'z' and all other 'c'
        
        if self.bucket_batch_size <= 0:        
            y_proc = self.caching(y_proc, y_on_cpu=y_on_cpu)
                      
        else:                    
            y_proc = self.caching([yi.reshape((-1)) for yi in y_proc], y_on_cpu=y_on_cpu)
            y_proc = y_proc.reshape((-1, self.bucket_batch_size))
        
        x_proc, y_proc, *z_proc              = shuffle_tensor_dataset(x_proc, y_proc, *z_proc) #only possible after str y is cached as tensor
        x, x_valid, y, y_valid, (z, z_valid) = self.valid_split(x_proc, y_proc, *z_proc, p_valid=p_valid)
                             
        ds       = TensorDataset(x, y, *z)
        ds_valid = TensorDataset(x_valid, y_valid, *z_valid)

        collate_fn = getattr(self, self.collate_fn)
        
        if self.params_config.dataset_to_gpu: 
            train_loader = DataLoader(dataset=ds      , batch_size=batch_size, shuffle=True, collate_fn=collate_fn)
            valid_loader = DataLoader(dataset=ds_valid, batch_size=batch_size, shuffle=True, collate_fn=collate_fn)

        else:              
            train_loader = DataLoader(dataset=ds      , batch_size=batch_size, shuffle=True, pin_memory=True, num_workers=12, collate_fn=collate_fn)
            valid_loader = DataLoader(dataset=ds_valid, batch_size=batch_size, shuffle=True, pin_memory=True, num_workers=12, collate_fn=collate_fn)

        self.dataloaders = DataLoaders(train_loader, valid_loader)        
        return self.dataloaders
    
    #-----------------------------------
    
    @staticmethod
    def from_datasets(datasets: list[Qc_Config_Dataset], balance_maxes: list, pad_constant, device: torch.device=torch.device("cpu"), bucket_batch_size=None, max_samples=None, **parameters):
        assert pad_constant != 0, "can NOT be 0! and not any other gate!"
        
        xs = []
        ys = []
        zs = []
        cs = []
        
        cut_multiple = Mixed_Cached_OpenClip_Dataset.cut_multiple
        
        max_qubits = max(dataset.params_config.num_of_qubits for dataset in datasets)
        max_gates  = max(dataset.params_config.max_gates     for dataset in datasets)
        max_gates  = int(np.ceil(max_gates /cut_multiple) * cut_multiple)
        
        parameters["num_of_qubits"]     = max_qubits
        parameters["max_gates"]         = max_gates
        parameters["random_samples"]    = sum([dataset.params_config.random_samples for dataset in datasets])
        parameters["min_gates"]         = min([dataset.params_config.min_gates      for dataset in datasets])
        parameters["comment"]           = f"Generated with 'from_datasets' with {len(datasets)} datasets. Qubits: {[dataset.params_config.num_of_qubits for dataset in datasets]}."
        parameters["pad_constant"]      = pad_constant
        parameters["bucket_batch_size"] = bucket_batch_size
         
        parameters["store_dict"] = {}
        for dataset in datasets:
            parameters["store_dict"] |= dataset.params_config.store_dict   #needs python 3.9 for union of dict  
        parameters["store_dict"]["z"]   = "tensor" #add special item

        if isinstance(max_samples, int):
            max_samples = [max_samples] * len(datasets)
        else:
            assert isinstance(max_samples, (list, np.ndarray))
            max_samples = np.array(max_samples, dtype=int)

        if isinstance(balance_maxes, int):
            balance_maxes = [balance_maxes] * len(datasets)
        else:
            assert isinstance(balance_maxes, (list, np.ndarray))
            balance_maxes = np.array(balance_maxes, dtype=int)
        
        for i, (dataset, balance_max) in tqdm(enumerate(zip(datasets,balance_maxes)), total=len(datasets)):
            # do x_y_preprocess now, we can't balance all together with mixed conditions
    
            dataset = dataset.to(device)
            
            x, y, *c = dataset.x_y_preprocess(balance_max=balance_max, max_samples=max_samples[i], shuffle=True)            
            x = x.to(device)    # [b, s, t]   
            
            print(f" - dataset size after balancing {x.shape[0]}")

            #-------
            # store original size
            z = torch.zeros((x.shape[0], 2), device=device, dtype=torch.int32)
            z[:, 0] = max(dataset.params_config.num_of_qubits, 1)
            
            red_x   = torch.sum(x.abs(), dim=1)          # [b, t]   .. collaps the zeros to get circuit length
            z[:, 1] = torch.count_nonzero(red_x, dim=1)  # [b]         
            z[z[:, 1]==0, 1] = 1 # make sure we don*t have 0, so we cheat and set it to 1 (there's only 1 unique zero gate circuit anyways). Needed for padding attn mask                 
            
            for i in range(x.shape[0]):
                x[i, z[i, 0]:,        :] = pad_constant
                x[i,        :, z[i, 1]:] = pad_constant
                
            z[:, 1] = (torch.ceil(z[:, 1] / cut_multiple) * cut_multiple).to(torch.int32) #for cut needs multiple

            #-------
            # now pad x, padding is defined from last dim forward!        
            pad = (0, max_gates-dataset.params_config.max_gates, 0, max_qubits-dataset.params_config.num_of_qubits) 
            x   = F.pad(x, pad, "constant", pad_constant)
                         
            # if c is missing something of the union we set it to a zero tensor
            for k,v in parameters["store_dict"].items(): 
                if k != "x" and k != "y" and k != "z":
                    
                    if k not in dataset.params_config.store_dict:
                        empty_tensor = torch.zeros((1,), device=device)
                        
                        if k == "U": #scetchy hardcoded for compilation
                            empty_tensor = torch.zeros((x.shape[0], 2, 1, 1), device=device) # unitary is [b, Re/Im, 2^n, 2^n]
                        
                        assert len(c) == 0
                        c.append(empty_tensor) #scetchy bcs if c is not empty we could break ordering!!!
                
            #combine datasets
            xs.append(x.cpu())  
            ys.append(y)
            zs.append(z) 
            cs.append([*c])

            dataset = dataset.to("cpu") #helps with gpu mem overflowing
        #-----------------

        has_U = "U" in parameters["store_dict"]
        has_p = "params" in parameters["store_dict"]
        
        if bucket_batch_size > 0:
            collate_fn_name = Mixed_Cached_OpenClip_Dataset.cut_padding_Bucket_collate_fn.__name__
            if has_U: 
                collate_fn_name = Mixed_Cached_OpenClip_Dataset.cut_padding_Bucket_collate_fn_compilation.__name__
                if has_p: 
                    collate_fn_name = Mixed_Cached_OpenClip_Dataset.cut_padding_Bucket_collate_fn_compilation_params.__name__
        
        else:
            collate_fn_name = Mixed_Cached_OpenClip_Dataset.cut_padding_collate_fn.__name__   
            if has_U: 
                collate_fn_name = Mixed_Cached_OpenClip_Dataset.cut_padding_collate_fn_compilation.__name__
                if has_p: 
                    collate_fn_name = Mixed_Cached_OpenClip_Dataset.cut_padding_collate_fn_compilation_params.__name__

        parameters["collate_fn"] = collate_fn_name
        
        #-----------------
        if bucket_batch_size > 0:
            for i, (xi,yi,zi, ci) in enumerate(zip(xs, ys, zs, cs)):  #cut rest of batch        
                b_mult = int(np.floor(xi.shape[0] / bucket_batch_size) * bucket_batch_size)  
                
                xs[i] = xi[None, :b_mult].reshape((b_mult//bucket_batch_size, bucket_batch_size, *xi.shape[1:])) 
                zs[i] = zi[None, :b_mult].reshape((b_mult//bucket_batch_size, bucket_batch_size, *zi.shape[1:]))
                
                t = parameters["store_dict"]["y"]
                if v == "tensor" or v == "numpy": 
                    ys[i] = yi[None, :b_mult].reshape((b_mult//bucket_batch_size, bucket_batch_size, *yi.shape[1:]))    
                else: raise NotImplementedError("")
            
                #----
                #For U, etc
                add_ind = 0
                for k,v in parameters["store_dict"].items(): 
                    if k != "x" and k != "y" and k != "z":                             
                        if v == "tensor" or v == "numpy": 
                            cs[i][add_ind] = ci[add_ind][None, :b_mult].reshape((b_mult//bucket_batch_size, bucket_batch_size, *ci[add_ind].shape[1:]))   
                        else: raise NotImplementedError("")                      
                        add_ind += 1                      
                      
        x = torch.cat(xs)
        y = ys                 # torch.cat(ys) is wrong,  y is list of numpy or str!! not a tensor
        z = torch.cat(zs)
        c = cs
        
        #-----------------    
        
        mixed_Cached_OpenClip_Dataset = Mixed_Cached_OpenClip_Dataset(device, **parameters)        
        mixed_Cached_OpenClip_Dataset.x = x
        mixed_Cached_OpenClip_Dataset.y = y
        mixed_Cached_OpenClip_Dataset.z = z
        
        add_ind = 0
        for k,v in parameters["store_dict"].items(): 
            if k != "x" and k != "y" and k != "z":   
                                     
                if v == "tensor" and k == "U":    # hardcoded U padding !!
                                           
                    n = sum([ci[add_ind].shape[0] for ci in c])
                    if bucket_batch_size > 0: shape = (n, bucket_batch_size, 2, 2**max_qubits, 2**max_qubits)
                    else:                     shape = (n,                    2, 2**max_qubits, 2**max_qubits)
                            
                    # allocating zeros is better memory wise than torch.cat(ci_s) and F.pad(ci, pad, "constant", 0)
                    mem = np.prod(shape) * c[0][add_ind].element_size() * 1e-9
                    print(f"[INFO]: allocate memory for {k} {shape} on {c[0][add_ind].device} approx. {mem:.3f} GB")
                    ci_s = torch.zeros(shape, device=c[0][add_ind].device)                 
                  
                    run_i = 0
                    for i,ci in enumerate(c):
                        ci = ci[add_ind]                                              
                        if bucket_batch_size > 0:  ci_s[run_i:run_i+ci.shape[0], :, :, :ci.shape[-2], :ci.shape[-1]] = ci                          
                        else:                      ci_s[run_i:run_i+ci.shape[0],    :, :ci.shape[-2], :ci.shape[-1]] = ci                 
                        run_i += ci.shape[0]

                elif v == "tensor" and k == "params": # hardcoded paramter padding !!

                    max_params = max(ci[add_ind].shape[-2] for ci in c)
                    
                    n = sum(ci[add_ind].shape[0] for ci in c)
                    if bucket_batch_size > 0: shape = (n, bucket_batch_size, max_params, max_gates)
                    else:                     shape = (n,                    max_params, max_gates)

                    # allocating zeros is better memory wise than torch.cat(ci_s) and F.pad(ci, pad, "constant", 0)
                    mem = np.prod(shape) * c[0][add_ind].element_size() * 1e-9
                    print(f"[INFO]: allocate memory for {k} {shape} on {c[0][add_ind].device} approx. {mem:.3f} GB")
                    ci_s = torch.zeros(shape, device=c[0][add_ind].device)                 
                  
                    run_i = 0
                    for i,ci in enumerate(c):
                        ci = ci[add_ind]                                              
                        if bucket_batch_size > 0:  ci_s[run_i:run_i+ci.shape[0], :, :ci.shape[-2], :ci.shape[-1]] = ci                          
                        else:                      ci_s[run_i:run_i+ci.shape[0],    :ci.shape[-2], :ci.shape[-1]] = ci                 
                        run_i += ci.shape[0]
                
                elif v == "numpy": raise NotImplementedError("")   
                else:              raise NotImplementedError("")           
                
                setattr(mixed_Cached_OpenClip_Dataset, str(k), ci_s)
                add_ind += 1
        
        return mixed_Cached_OpenClip_Dataset
    
    #------------------------------------
    
    # def plot_example(self):     print("plot_example not implemented for Mixed_Cached_OpenClip_Dataset")
    # def plot_distribution(self): print("plot_distribution not implemented for Mixed_Cached_OpenClip_Dataset")
    
    @staticmethod
    def from_config_file(config_path, device: torch.device, save_path: str=None):
        config = load_config(config_path)
        config["target"] = class_to_str(Mixed_Cached_OpenClip_Dataset)               
        return Config_Dataset.from_config(config, device, save_path)