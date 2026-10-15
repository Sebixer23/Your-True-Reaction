# Lupi's Idea / Nana's Despair / Claude's finisher

**Your True Reaction** is a reaction time test made with pygame. Click the CLICK color 5 times to get your average reaction time. Click the AVOID color, or click too early, and you start over. The cog in the top right corner lets you pick the CLICK and AVOID colors: red, green, blue or yellow (they can't be the same).

## Download

Get `YourTrueReaction.exe` from the [Releases](https://github.com/Sebixer23/Your-True-Reaction/releases) page. Nothing to install, just run it.

The first time, Windows will probably show "Windows protected your PC" because the exe isn't code signed. Click **More info**, then **Run anyway**.

## Is the exe safe?

You don't have to take my word for it:

- **All the code is here.** The whole game is the one `.py` file in this repo, so you can read exactly what it does.
- **The exe isn't built on my PC.** GitHub builds it straight from this code using [this workflow](.github/workflows/build-exe.yml), and every release links to its build log.
- **GitHub signs every build.** Each exe gets an attestation that proves it was built by this repo's workflow from a specific commit. With the [GitHub CLI](https://cli.github.com/) you can check it yourself:

  ```
  gh attestation verify YourTrueReaction.exe -R Sebixer23/Your-True-Reaction
  ```

- **You can check the checksum.** In PowerShell run `Get-FileHash YourTrueReaction.exe` and compare it with `SHA256SUMS.txt` on the release page.

The game never connects to the internet. The only file it writes is your color settings, at `%APPDATA%\ReactChatter\settings.json`.

## Run from source

Install pygame with `pip install pygame`, then run the `.py` file with Python.
