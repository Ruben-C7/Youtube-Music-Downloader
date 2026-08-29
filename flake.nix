{
  description = "YT Music Downloader for Jellyfin/Navidrome";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs =
    { self, nixpkgs }:
    let
      supportedSystems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
    in
    {
      packages = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          pythonEnv = pkgs.python3.withPackages (
            ps: with ps; [
              yt-dlp
              python-dotenv
            ]
          );
        in
        {
          default = pkgs.writeShellApplication {
            name = "yt-music-downloader";
            runtimeInputs = [
              pythonEnv
              pkgs.ffmpeg_7-headless
            ];
            text = ''
              python ${./main.py} "$@"
            '';
          };
        }
      );

      apps = forAllSystems (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/yt-music-downloader";
        };
      });
    };
}
