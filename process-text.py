import html
import json
import os
import pprint
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import JavaScriptCore
import pygments
from pygments import lexers
from pygments.formatters import HtmlFormatter
from pygments.lexer import Lexer

from eval_with_auto_import import eval_with_auto_import

TEXT_INPUT_FILE = "/tmp/in.txt"
TEXT_OUTPUT_FILE = "/tmp/out.txt"
HTML_OUTPUT_FILE = "/tmp/out.txt.html"
CSS_FILE = "process-text.css"
DUAL_PANE_LINE_WIDTH = 59

PYGMENTS_STYLE = "material"
PYGMENTS_FORMATTER = HtmlFormatter(
    style=PYGMENTS_STYLE,
    full=True,
    noclasses=True,
)


@dataclass
class Output:
    _text: str = ""
    lexer: Lexer = lexers.TextLexer()
    err: Optional[str] = None
    title: str = ""
    subtitle: str = ""

    @property
    def text(self) -> str:
        return self._text if self._text else contents(TEXT_OUTPUT_FILE)

    @text.setter
    def text(self, value: str):
        if value.strip():
            write(TEXT_OUTPUT_FILE, value)
        self._text = value

    @property
    def err_html(self) -> str:
        if self.err is None:
            return ""
        return f'<code id="err">{html.escape(self.err)}</code>'

    @property
    def output_html(self) -> str:
        faded = 'class="faded"' if self.err else ""
        txt = pygments.highlight(self.text, self.lexer, PYGMENTS_FORMATTER)
        return f'<code id="out" {faded}>{txt}</code>'


# If we don't know whether the text is JSON, CSV, markdown, or some other
# format, still, would be good to have some syntax highlighting, so we let
# pygments guess the lexer.
def hilight_best_effort(txt: str) -> str:
    try:
        json.loads(txt)
        lexer = lexers.JsonLexer()
    except:
        lexer = lexers.guess_lexer(txt)
    return pygments.highlight(txt, lexer, PYGMENTS_FORMATTER)


def contents(filepath: str) -> str:
    with open(filepath, "r") as f:
        return f.read()


def write(filepath: str, content: str) -> None:
    with open(filepath, "w") as f:
        f.write(content)


def py_json(json_str: str, py_code: str) -> Output:
    """Process JSON string using Python code."""
    output = Output(
        title="Process JSON with Python",
        subtitle="variable: j (parsed JSON object)",
    )

    try:
        j = json.loads(json_str)
    except Exception as e:
        output.err = str(e)
        return output

    # Question mark means the user wants to inspect and look at the docs
    if py_code.endswith("?"):
        py_code = f"wat_inspect.inspect_format({py_code[:-1]})"
        # "wat" formats the docs in a way that goes well with python syntax
        # highlighter.
        output.lexer = lexers.Python3Lexer()

    try:
        result = eval_with_auto_import(py_code, globals(), locals())
    except Exception as e:
        output.err = str(e)
        return output

    if type(result) is str:
        output.text = result
        try:
            json.loads(result)
            output.lexer = lexers.JsonLexer()
        except:
            pass
    else:
        try:
            # If the result is serializable to JSON, pretty-print it.
            # After all, we're transforming JSON. This allows us to skip typing
            # json.dumps() in Alfred.
            output.text = json.dumps(result, indent=2)
            output.lexer = lexers.JsonLexer()
        except:
            output.text = pprint.pformat(
                result,
                width=55,
                indent=2,
                compact=True,
            )
            # Pretty-printed python objects are, almost always, valid python.
            output.lexer = lexers.Python3Lexer()
    return output


def py_txt(txt: str, py_code: str) -> Output:
    """Process text using Python code."""
    output = Output(
        title="Process Text with Python",
        subtitle="variable: txt",
    )

    # Question mark means the user wants to inspect and look at the docs
    if py_code.endswith("?"):
        py_code = f"wat_inspect.inspect_format({py_code[:-1]})"
        # "wat" formats the docs in a way that goes well with python syntax
        # highlighter.
        output.lexer = lexers.Python3Lexer()

    try:
        result = eval_with_auto_import(py_code, globals(), locals())
    except Exception as e:
        output.err = str(e)
        return output

    if type(result) is str:
        output.text = result
    else:
        output.text = pprint.pformat(
            result,
            width=DUAL_PANE_LINE_WIDTH,
            indent=2,
            compact=True,
        )
        # Pretty-printed python objects are, almost always, valid python.
        output.lexer = lexers.Python3Lexer()
    return output


def shell_txt(txt: str, shell_code: str) -> Output:
    """Process text using shell commands."""
    output = Output(
        title="Process Text with Shell Commands",
        subtitle='variable: "$txt" (use ? for man page eg. `ls | cut?`)',
    )
    env = os.environ.copy()
    env["txt"] = txt
    if shell_code.endswith("?"):
        doc_cmd = shell_code[:-1].split()[-1]
        env["MANWIDTH"] = str(DUAL_PANE_LINE_WIDTH)
        shell_code = shell_code.replace(
            f"{doc_cmd}?",
            f"man {doc_cmd} | col -bx",
        )

    result = subprocess.run(
        shell_code,
        shell=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        output.err = result.stdout + "\n" + result.stderr
    else:
        output.text = result.stdout
    return output


def jsc_json(json_str: str, js_code: str) -> Output:
    """Process JSON string using JavaScriptCore (jsc)"""
    output = Output(
        title="Process JSON with JavaScript",
        subtitle="variable: j (parsed JSON object)",
    )
    jsc = JavaScriptCore.JSContext.new()
    jsc.evaluateScript_(f"let j = {json_str};")
    result = jsc.evaluateScript_(f"JSON.stringify({js_code})")
    if jsc.exception():
        output.err = jsc.exception().toString()
        return output
    output.text = result.toString()
    try:
        output.text = json.dumps(json.loads(output.text), indent=2)
        output.lexer = lexers.JsonLexer()
    except:
        output.lexer = lexers.JavascriptLexer()
    return output


def jq(json_str: str, jq_filter: str) -> Optional[str]:
    """Process JSON string using jq."""
    output = Output(title="Process JSON with jq")
    process = subprocess.Popen(
        ["jq", jq_filter],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out, err = process.communicate(json_str)
    if err:
        output.err = err
    else:
        output.text = out
        output.lexer = lexers.JsonLexer()
    return output


def alfred_html(in_txt: str, output: Output) -> str:
    """Generate Alfred HTML output."""
    return f"""
    <html>
      <head>
        <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
        <style>{contents(CSS_FILE)}</style>
      </head>
      <body>
        <div class="input">
          <code>{hilight_best_effort(in_txt)}</code>
        </div>
        <div class="output">
          {output.output_html}
          {output.err_html}
        </div>
      </body>
    </html>
    """


def main():
    in_txt = contents(TEXT_INPUT_FILE)

    if not Path(TEXT_OUTPUT_FILE).exists():
        write(TEXT_OUTPUT_FILE, in_txt)

    funcname, code = sys.argv[1], sys.argv[2]
    output = globals()[funcname](in_txt, code)

    write(HTML_OUTPUT_FILE, alfred_html(in_txt, output))
    json.dump(
        {
            "items": [
                {
                    "title": output.title,
                    "subtitle": output.subtitle,
                    "arg": output.text,
                    "quicklookurl": HTML_OUTPUT_FILE,
                    "text": {
                        "largetype": output.err,
                    },
                },
            ]
        },
        sys.stdout,
        indent=2,
    )


if __name__ == "__main__":
    main()
