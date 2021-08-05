from jinja2 import Template

_str = """
{% for modality_name, modality_value in _dict.items() %}
## {{modality_name}}
    {% for type_name, type_dict in modality_value['data'].items() %}
### {{type_name}}
        {% for format_name, format_dict in type_dict.data.items() %}
#### {{format_name}}
```python
from {{modality_value.repo}} import Nwb{{type_name}}Extractor, {{format_dict.extractor}}

{{type_dict.object_name}} = {{format_dict.extractor}}("{{format_dict.dataset_path_arg}}")
{{type_dict.nwb_converter_class_name}}.{{type_dict.method_name}}({{type_dict.object_name}}, "output_path.nwb")
```
        {% endfor %}
    {% endfor %}
{% endfor %}    
"""

_dict = {
    "Extracellular electrophysiology": dict(repo="spikeextractors", data=dict(Recording=dict(data=dict()))),
    "Optical physiology": dict(
        repo="roiextractors",
        data=dict(
            Imaging=dict(
                nwb_converter_class_name="NwbImagingExtractor",
                method_name="write_imaging",
                object_name="imaging_ex",
                data=dict(Tiff=dict(extractor="TiffImagingExtractor", dataset_path_arg="imaging.tiff")),
            ),
            Segmentation=dict(
                nwb_converter_class_name="NwbSegmentationExtractor",
                method_name="write_segmentation",
                object_name="seg_ex",
                data=dict(
                    CaImAn=dict(extractor="CaimanSegmentationExtractor", dataset_path_arg="caiman_analysis.hdf5")
                ),
            ),
        ),
    ),
}

template = Template(_str)
print(template.render(_dict=_dict))
