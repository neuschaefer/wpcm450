# Third-party tools and documentation for the Nuvoton WPCM450 BMC

- [tools](./tools/): Tools that run on any workstation
- [src](./src/): Code that can run on the BMC
  - [bare-metal/monitor](./src/bare-metal/monitor.c): A [machine monitor](https://en.wikipedia.org/wiki/Machine_code_monitor)
    program that lets you peek, poke and copy memory, as well as run code.
    It can also act as a primitive bootloader.
  - [linux](./src/linux): Tools that run under Linux
  - [dellfw](./src/dellfw): Tools that help with reverse-engineering Dell firmware
- My Linux patches are in [neuschaefer/linux](https://github.com/neuschaefer/linux/tree/wpcm)

Hardware documentation is [in the wiki](https://github.com/neuschaefer/wpcm450/wiki/) ([GitLab mirror](https://gitlab.com/neuschaefer/wpcm450/-/wikis/home), [Codeberg mirror](https://codeberg.org/neuschaefer/wpcm450/wiki/Home)).

This reposity is available on [GitHub](https://github.com/neuschaefer/wpcm450/), [GitLab](https://gitlab.com/neuschaefer/wpcm450/), and [Codeberg](https://codeberg.org/neuschaefer/wpcm450).

To discuss a specific mainboard, please find the corresponding
[issue](https://github.com/neuschaefer/wpcm450/issues?q=is%3Aopen+is%3Aissue+label%3A%22New+board%22)
or open a new one.

If you want to talk on IRC, join [`##ehh`](https://web.libera.chat/##ehh)
on [Libera.Chat](https://libera.chat).
