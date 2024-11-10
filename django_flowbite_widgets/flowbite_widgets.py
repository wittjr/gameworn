from django import forms
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.conf.urls.static import static
import json


class FlowbiteTextInput(forms.widgets.TextInput):
    class Media:
        css = {}
        js = []

    def __init__(self, attrs=None, options={}):
        self.options = options
        super().__init__(attrs)
        self.attrs.update(
            {
                "class": "bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
            }
        )


class FlowbiteNumberInput(forms.widgets.NumberInput):
    class Media:
        css = {}
        js = []

    def __init__(self, attrs=None, options={}):
        self.options = options
        super().__init__(attrs)
        self.attrs.update(
            {
                "class": "bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
            }
        )


class FlowbiteSelectInput(forms.widgets.Select):
    class Media:
        css = {}
        js = []

    def __init__(self, attrs=None, options={}):
        self.options = options
        super().__init__(attrs)
        self.attrs.update(
            {
                "class": "bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
            }
        )


class FlowbiteCheckboxInput(forms.widgets.CheckboxInput):
    class Media:
        css = {}
        js = []

    def __init__(self, attrs=None, options={}):
        self.options = options
        super().__init__(attrs)
        self.attrs.update(
            {
                "class": "w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 dark:focus:ring-blue-600 dark:ring-offset-gray-800 focus:ring-2 dark:bg-gray-700 dark:border-gray-600"
            }
        )


class FlowbiteTextarea(forms.widgets.Textarea):
    class Media:
        css = {}
        js = []

    def __init__(self, attrs=None, options={}):
        self.options = options
        super().__init__(attrs)
        self.attrs.update(
            {
                "class": "block p-2.5 w-full text-sm text-gray-900 bg-gray-50 rounded-lg border border-gray-300 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
            }
        )


class FlowbiteImageDropzone(forms.widgets.FileInput):
    template_name = "django_flowbite_widgets/image_dropzone.html"

    class Media:
        css = {}
        js = ["django_flowbite_widgets/image_dropzone.js"]

    def __init__(self, attrs=None, options={}):
        self.options = options
        super().__init__(attrs)

    def get_context(self, name, value, attrs):
        current_class = attrs.get("class")
        custom_class = "custom-dropzone-widget-" + name

        if current_class:
            attrs["class"] = current_class + " " + custom_class
        else:
            attrs["class"] = custom_class

        context = super(FlowbiteImageDropzone, self).get_context(name, value, attrs)
        context["label"] = "Test"
        context["name"] = name
        #   attrs = self.build_attrs(attrs, name=name)
        self.options.update({"class": custom_class, "paramName": name})

        context["widget"] = {
            "name": name,
            "attrs": self.build_attrs(extra_attrs=attrs, base_attrs=attrs),
        }

        context["options"] = json.dumps(self.options)
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
