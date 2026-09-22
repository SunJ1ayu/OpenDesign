# 整屏截图 + 白屏体检读数(算法同旧 windows-package-probe.ps1 的 Test-Blankness:中心 60% 区域每 5px 采样,颜色按 16 级量化)。
# 用法:pwsh -File shot.ps1 <输出 png>;打印一行 JSON {colors, whitePct}。
# 云 Windows 判据 E2.repaint 拿 colors 判「托盘还原后只剩底色」(挑战 #17):纯底色 ≈ 1~2 种,有界面远多于此。
param([Parameter(Mandatory)][string]$Path)
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
$b = [System.Windows.Forms.SystemInformation]::VirtualScreen
$bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
$bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose()
$x0 = [int]($bmp.Width * 0.2); $x1 = [int]($bmp.Width * 0.8)
$y0 = [int]($bmp.Height * 0.2); $y1 = [int]($bmp.Height * 0.8)
$seen = @{}; $white = 0; $n = 0
for ($y = $y0; $y -lt $y1; $y += 5) {
    for ($x = $x0; $x -lt $x1; $x += 5) {
        $p = $bmp.GetPixel($x, $y); $n++
        $seen["{0}-{1}-{2}" -f [int]($p.R / 16), [int]($p.G / 16), [int]($p.B / 16)] = 1
        if ($p.R -ge 235 -and $p.G -ge 235 -and $p.B -ge 235) { $white++ }
    }
}
$bmp.Dispose()
@{ colors = $seen.Count; whitePct = [Math]::Round(100.0 * $white / $n, 1) } | ConvertTo-Json -Compress
