from django import forms
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.conf.urls.static import static
import json

class SpecifyImageWidget(forms.widgets.FileInput):
    template_name = 'memorabilia/specify_image_widget.html'

    class Media:
      # js = ['memorabilia/specify_image_widget.js']
      css = {}
      js = ['memorabilia/specify_image_widget.js']


    def __init__(self, attrs=None, options={}):
        self.options = options
        super().__init__(attrs)


    def get_context(self, name, value, attrs):
        current_class = attrs.get('class')
        custom_class = 'custom-dropzone-widget-' + name

        if current_class:
            attrs['class'] = current_class + ' ' + custom_class
        else:
            attrs['class'] = custom_class

        context = super(SpecifyImageWidget, self).get_context(name, value, attrs)
        context['label'] = 'Test'
        context['name'] = name
      #   attrs = self.build_attrs(attrs, name=name)
        self.options.update({
            'class': custom_class,
            'paramName': name
        })

        context['widget'] = {
            'name': name,
            'attrs': self.build_attrs(extra_attrs=attrs, base_attrs=attrs),
        }

        context['options'] = json.dumps(self.options)
      #   context['options'] = self.options
        return context

    # def render(self, name, value, attrs={}):
    #     context = self.get_context(name, value, attrs)
    #     return mark_safe(render_to_string(self.template_name, context))
    
    # def __init__(self, attrs=None, *args, **kwargs):
    #     print('init')
    #     print(self)
    #     print(attrs)
    #     # super().__init__(attrs)

    # def decompress(self, value):
    #     print('decompress')
    #     print(value)
    #     return []

    # def __init__(self, attrs=None):
    #     widgets = [
    #         forms.URLInput(attrs=attrs),
    #         forms.FileInput(attrs=attrs),
    #     ]
    #     super(SpecifyImageWidget, self).__init__(widgets, attrs)