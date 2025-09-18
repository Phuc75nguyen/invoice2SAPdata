"""
Generic extraction helpers.

The :mod:`invoice2SAPdata.invoice_parsers` package contains
specialised parsers for each telecom provider. In some cases you may
want to extract generic fields that appear across multiple invoice
formats, such as invoice numbers, dates or totals. This module
provides a placeholder for such utility functions. At present
``extract_fields`` simply returns an empty dict, but you can extend
it with common regex patterns or text‑processing logic to suit
additional providers or use cases.

If you decide to use this helper, make sure to call it from your
parser implementations and merge its output with provider‑specific
fields. For example:

    data = extract_fields(page_text)
    provider_data.update(data)
    return provider_data
"""

def extract_fields(text: str) -> dict:
    """Placeholder for future extraction logic.

    Parameters
    ----------
    text : str
        Raw text extracted from a PDF page.

    Returns
    -------
    dict
        An empty dictionary at present. Extend this function to return
        extracted key–value pairs from the text.
    """
    # TODO: implement generic field extraction (if needed)
    return {}