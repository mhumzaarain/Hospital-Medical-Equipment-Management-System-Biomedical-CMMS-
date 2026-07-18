from django.contrib.auth.forms import AuthenticationForm

INPUT = (
    "w-full rounded border border-slate-300 px-3 py-2 "
    "focus:border-sky-500 focus:outline-none"
)


class StyledAuthenticationForm(AuthenticationForm):
    """Login form with the app's Tailwind input styling (the default widgets
    render borderless, which Tailwind's reset makes invisible)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT
