# SmartDict

## Usage

- String as references of another item

## Install 

`pip install smartdict`

## Description

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
```
