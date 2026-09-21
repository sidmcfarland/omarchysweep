# Publishing to the AUR

`omarchysweep-git` builds straight from `main`, so it never needs a version
bump — only a `.SRCINFO` refresh when the `PKGBUILD` itself changes.

Build and install it locally first:

```bash
cd packaging/aur/omarchysweep-git
makepkg -si
```

Publishing needs an [AUR account](https://aur.archlinux.org/register) with your
SSH public key added under *My Account → SSH Public Key*. Then:

```bash
git clone ssh://aur@aur.archlinux.org/omarchysweep-git.git
cd omarchysweep-git
cp /path/to/OmarchySweep/packaging/aur/omarchysweep-git/PKGBUILD .
makepkg --printsrcinfo > .SRCINFO
git add PKGBUILD .SRCINFO
git commit -m "Initial import: omarchysweep-git"
git push
```

The AUR rejects a push whose `.SRCINFO` does not match the `PKGBUILD`, so
regenerate it every time you touch the build.

Once it is up, Omarchy users install the game with:

```bash
omarchy pkg aur add omarchysweep-git
```

## A tagged release instead

For a stable, non-`-git` package, tag a release and swap these lines into a
copy named `omarchysweep`:

```bash
pkgname=omarchysweep
pkgver=1.0.0
source=("$pkgname-$pkgver.tar.gz::$url/archive/refs/tags/v$pkgver.tar.gz")
sha256sums=('<sha256 of the tarball>')
```

Drop the `pkgver()` function, the `provides`/`conflicts` pair and the `git`
makedepend, and point `cd` at `$srcdir/$pkgname-$pkgver`.
