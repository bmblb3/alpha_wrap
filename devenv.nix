{ pkgs, ... }:

{
  # Python env for sweep.py (matplotlib uses the headless Agg backend)
  languages.python = {
    enable = true;
    package = pkgs.python312;
    venv.enable = true;
    venv.requirements = ./requirements.txt;
  };

  enterShell = ''
    echo "sweep.py env ready: python $(python --version | cut -d' ' -f2)"
  '';
}
