# crawler
This tool was written to crawling usage of Javascript-plugins on sites.
## Installation
### via Git clone
- Clone this repository
```
git clone https://github.com/dsp25no/crawler.git
```
- install python requirements (support only python3)
```
cd crawler
pip install -r requirements.txt
```
- [install](http://splash.readthedocs.io/en/stable/install.html) docker with splash image (support docker from 1.21)

## Usage
```
Usage: crawler.py [OPTIONS] TARGETS_LIST

Options:
  --debug             Include this flag to enable debug messages.
  --filters FILENAME  File with filters to find metrics.  [required]
  --offline           Include this flag lo load hars from save.
  -h, --help          Show this message and exit.
  ```
Format of filters:
```
#This is comment
filter_name regular_expression_for_filter
```
Format of targets list:
```
{ "Target_class": [
    {
      "name" : "target name",
      "url" : "optional url of target",
      "param" : "optional param",
      "another param" : "another optional param"
    }
    ...
  ],
  "Another_target_class": [
    ...
  ]
}
```
**_Target_class_** must inherit **_Target_** and file with code of class must be in directory **_targets_**

## Example
- Check that docker daemon is running
- Copy files from one of the **_examples_** subdirectories to the tool's directory
- Run tool:
```
python crawler.py --filters filters.txt targets.json
```
