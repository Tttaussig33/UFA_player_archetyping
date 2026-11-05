"""Package the local extension without installing build dependencies."""
from pathlib import Path
import json
import zipfile
from xml.sax.saxutils import escape

root = Path(__file__).resolve().parent
extension = root / 'extension'
package = json.loads((extension / 'package.json').read_text())
manifest = f'''<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011">
 <Metadata>
  <Identity Language="en-US" Id="{package['name']}" Version="{package['version']}" Publisher="{package['publisher']}" />
  <DisplayName>{escape(package['displayName'])}</DisplayName>
  <Description xml:space="preserve">{escape(package['description'])}</Description>
  <Tags>UFA,research,preview</Tags><Categories>Visualization</Categories><GalleryFlags>Public</GalleryFlags>
  <Properties>
   <Property Id="Microsoft.VisualStudio.Code.Engine" Value="{package['engines']['vscode']}" />
   <Property Id="Microsoft.VisualStudio.Code.ExtensionDependencies" Value="" />
   <Property Id="Microsoft.VisualStudio.Code.ExtensionPack" Value="" />
   <Property Id="Microsoft.VisualStudio.Code.LocalizedLanguages" Value="" />
   <Property Id="Microsoft.VisualStudio.Code.EnabledApiProposals" Value="" />
   <Property Id="Microsoft.VisualStudio.Code.ExecutesCode" Value="true" />
  </Properties>
  <License>extension/LICENSE</License>
 </Metadata>
 <Installation><InstallationTarget Id="Microsoft.VisualStudio.Code" /></Installation>
 <Dependencies />
 <Assets><Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true" />
 <Asset Type="Microsoft.VisualStudio.Services.Content.Details" Path="extension/README.md" Addressable="true" />
 <Asset Type="Microsoft.VisualStudio.Services.Content.License" Path="extension/LICENSE" Addressable="true" /></Assets>
</PackageManifest>'''
content_types = '''<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="json" ContentType="application/json" />
 <Default Extension="js" ContentType="application/javascript" />
 <Default Extension="cjs" ContentType="application/javascript" />
 <Default Extension="css" ContentType="text/css" />
 <Default Extension="txt" ContentType="text/plain" />
 <Default Extension="md" ContentType="text/markdown" />
 <Default Extension="vsixmanifest" ContentType="text/xml" />
 <Override PartName="/extension/LICENSE" ContentType="text/plain" />
</Types>'''
target = root / f"ufa-research-preview-{package['version']}.vsix"
with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
    archive.writestr('extension.vsixmanifest', manifest)
    archive.writestr('[Content_Types].xml', content_types)
    for file in sorted(extension.rglob('*')):
        if file.is_file():
            archive.write(file, 'extension/' + str(file.relative_to(extension)))
print(target)
