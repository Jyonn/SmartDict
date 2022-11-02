# SmartDict

## Usage

- String as references of another item

## Install 

`pip install smartdict`

## Description

### Normal String-based Referencing `${}`

```python
import smartdict

data = {
    "dataset": "spotify",
    "load": {
        "base_path": "~/data/${dataset}",
        "train_path": "${load.base_path}/train",
        "dev_path": "${load.base_path}/dev",
        "test_path": "${load.base_path}/test",
    },
    "network": {
        "num_hidden_layers": 3,
        "num_attention_heads": 8,
        "hidden_size": 64,
    },
    "store": "checkpoints/${dataset}/${network.num_hidden_layers}L${network.num_attention_heads}H/"
}

data = smartdict.parse(data)
print(data['load']['base_path'])  # => ~/data/spotify
print(data['load']['dev_path'])  # => ~/data/spotify/dev
print(data['store'])  # => checkpoints/spotify/3L8H/

# feel free to use oba.Obj

from oba import Obj
data = Obj(data)
print(data.load.base_path)  # => ~/data/spotify
print(data.load.dev_path)  # => ~/data/spotify/dev
print(data.store)  # => checkpoints/spotify/3L8H/
```

### Full-Match Referencing `${}$`

```python
import oba
import smartdict

data = dict(
    a='${b.v.1}+1',  # normal referencing
    b='${c}$',  # full-match referencing, supported by smartdict>=0.0.4 
    c=dict(
        l=23,
        v=('are', 'you', 'ok'),
    )
)

data = smartdict.parse(data)
print(data['b'])  # => {'l': 23, 'v': ('are', 'you', 'ok')}

data = oba.Obj(data)
print(data.a)  # => you+1
print(data.b.l)  # => 23
```

### Fancy Class Referencing

```python
import smartdict
import random

import string


class Rand(dict):  # if you want to further be JSON stringify, please derive your class from dict, list, etc. 
    """
    get random string of n length by Rand()[n]
    """
    chars = string.ascii_letters + string.digits

    def __init__(self):
        super(Rand, self).__init__({})

    def __getitem__(self, item):
        return ''.join([random.choice(self.chars) for _ in range(int(item))])
    
    def __contains__(self, item):
        return True


data = dict(
    filename='${utils.rand.4}',  # fancy referencing, supported by smartdict>=0.0.4
    utils=dict(
        rand=Rand(),
    )
)
data = smartdict.parse(data)


print(data['filename'])  # => toXE (random string with length 4)
```