# SmartDict

## Usage

- String as references of another item

## Install 

`pip install smartdict`

## Description

```python
data = {
	'player': {
		'name': 'DiscreteTom',
		'items': [
			'@{potion.red}'
		],
		'weapon': '@{sword}',
		'attack': '@{player.weapon.attack}',
		'me': '@{player}'
	},
	'potion': {
		'red': 'restore your health by 20%',
	},
	'sword': {
		'attack': 123
	},
}
```