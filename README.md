### penpal

`penpal` is a literate programming tool that I've written for my own use when writing technical content. For more information, see [Writing about writing about programming](https://axleos.com/writing-about-writing-about-programming/).

I'm currently using `$! ... !$` as penpal's command delimiters, and I chose this to avoid conflicts. `{{ ... }}` conflicts with Hugo shortcodes, and `<< ... >>` conflicts with Rust types. If needed, the delimiter sequences can easily be swapped out in `MarkdownParser.BEGIN_COMMAND_SEQ` and `MarkdownParser.END_COMMAND_SEQ`. 

### Example

The input to `penpal` is markup containing regular markdown and `penpal`-specific commands. The `penpal` commands allow the prose to define 'snippets' that can be referenced, embedded, and updated. 

When the `generate` command is used, the current state of every snippet is rendered into a source code tree. 

When `penpal-cli.py` is run, `penpal` will preprocess the markup and will `generate` source trees as described above. As a second output, `penpal` will also pretty-print the snippets, in context, in a markdown/Hugo-shortcode blend that's suitable for embedded in the axle blog. With minor tweaks to the code, it'd output plain markdown, or any other format - the exact output format for the final prose document is pretty flexible. 

```text
This is some prose explaining the code.

$!define main_rs
file: src/main.rs
lang: rust
###
$!imports!$

fn main() {
    println!("Hello, world!");
$!main_part2!$
}
```

The command below will print the above snippet, hiding snippets that haven't been defined such as `imports` and `main_part2`.

```text
$!show main_rs!$
```

This will cause the snippet at the top to be rendered to markdown like so:

```text
```rust

fn main() {
    println!("Hello, world!");
}
```
```

We can then define some of the snippets we mentioned earlier:

```text
$!define imports
lang: rust
###
use std::io;
!$

$!show imports!$
```

We can also update snippets after defining them:

```text
$!update imports
use std::io;
use std::fmt::{Display, Formatter};
!$
```

`update` will automatically render a highlighted diff block, whereas with `define` you need to explicitly `show` the snippet.

Lastly, use `generate` to collect all the snippets together into a source tree. `generate` can be used several times at different points throughout the prose, to produce many versions of a program that matches the progress made through the prose so far -- this is the point of `penpal`! It allows me to write a post that describes the construction of a program, with guarantees that I'm not going to forget to carry an edit forwards, and ensuring that the code is compilable and works as expected at every `generate` checkpoint.

### License

MIT license
