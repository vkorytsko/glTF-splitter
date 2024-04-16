# glTF-splitter
Splits asset's buffers into chunks according to provided maximum size. Does not rearrange existing buffers, but only splits ones over the limit. **CARE**: the script modifies given resources.

## Arguments
- `-p`, `--path`: Path to glTF asset - required;
- `-l`, `--limit`: Size limit for included binary buffers (.bin, .glbin, or .glbuf). 0 to split by each view. Note: size should be grater or equal than the largest view - optional - default=0;
- `-f`, `--format`: Pretty print resulting gltf - optional - default=false;
- `-v`, `--verbose`: Detailed logging - optional - default=false.

## Usage
Has been developed using Python 3.12.3 and tested on the limited set of input models. Some glTF features could not been supported.
#### Example
```git
python -p=".\path\to\file.gltf" -l=1024000 -f -v
```
