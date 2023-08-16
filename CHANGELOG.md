<!--next-version-placeholder-->

## v0.6.2 (2023-08-16)
### Fix

* **nuke:** Add platform specific paths ([`39de801`](https://github.com/beatreichenbach/realflare/commit/39de8010c5dcee5671bce47b8a300df47cd69322))

## v0.6.1 (2023-07-17)
### Fix

* **nuke:** Remove dev path and add os specific flags ([`d914cb4`](https://github.com/beatreichenbach/realflare/commit/d914cb49cd1472dbca5b00b8234894571decbb49))
* **opencl:** Define constants with __constant ([`93eaff4`](https://github.com/beatreichenbach/realflare/commit/93eaff4de521152bbff08c9cace06174ae53d8d2))

## v0.6.0 (2023-07-02)
### Feature

* **nuke:** Add plugin ([`b22dbe4`](https://github.com/beatreichenbach/realflare/commit/b22dbe4af29f65cb7b306d905843d089dd12187e))
* **api:** Optimizations/cleanup/caching ([`82fa1e1`](https://github.com/beatreichenbach/realflare/commit/82fa1e180d4b84d8cd62d7c591112991f93efce6))

### Fix

* **nuke:** Update menu ([`1fe3538`](https://github.com/beatreichenbach/realflare/commit/1fe353816728f0f13b94894851c119a975015bd5))
* **nuke:** Add zip and clean plugin ([`529ad6b`](https://github.com/beatreichenbach/realflare/commit/529ad6b4deac3393c6d7de636d71480bc9b783dd))
* **benchmark:** Update ([`a33fe1f`](https://github.com/beatreichenbach/realflare/commit/a33fe1fe262e2549b412c371bf455f20c70bb6f6))

## v0.5.0 (2023-06-19)
### Feature

* **engine:** Add animation ([`09cd910`](https://github.com/beatreichenbach/realflare/commit/09cd910923c0f7f033ad3b6ff0c7c03ff9a4f3b6))
* **engine:** Add compositing ([`8097e8f`](https://github.com/beatreichenbach/realflare/commit/8097e8f22c348a91da6b51f052d36a1470f9224f))
* **engine:** Add aperture/starburst parameters ([`27a08b1`](https://github.com/beatreichenbach/realflare/commit/27a08b123b50668a6017e2e0c16edfc0bd684115))
* **engine:** Add starburst/aperture parameters ([`b700119`](https://github.com/beatreichenbach/realflare/commit/b700119cc4131f7c401af1a3c270d4af4db79bbb))
* **nuke:** Initial nuke gizmo ([`ffcf99b`](https://github.com/beatreichenbach/realflare/commit/ffcf99bcbcb02fe2dad688964a63f0fb9bb89a63))

### Fix

* **engine:** Emit_image cache ([`6c1d1fc`](https://github.com/beatreichenbach/realflare/commit/6c1d1fcb945e8cc48b942bbc89e753ffb2bdc464))
* **diagram:** Match latest project config ([`8b1b031`](https://github.com/beatreichenbach/realflare/commit/8b1b03159ab2137e3acc0c44ce4c169eb263646f))
* **lens model editor:** Match refactor of qt_extension ([`c85f366`](https://github.com/beatreichenbach/realflare/commit/c85f366217f45f538fe48a82525c83dd9e96d3d3))

## v0.4.4 (2023-06-01)
### Fix

* Make python 3.9 compatible ([`d188d9e`](https://github.com/beatreichenbach/realflare/commit/d188d9e516fe15933b0e7f93b8a17c6258e36f20))
* **engine:** Convert to acescg in render ([`68df2a8`](https://github.com/beatreichenbach/realflare/commit/68df2a8954f27dfe5ca84011b63e0f69ee47d9d7))
* **storage:** Add ocio support ([`5cdf593`](https://github.com/beatreichenbach/realflare/commit/5cdf593ca62e3e1390dc960b131c192906939525))
* **engine:** Handle cv2 errors ([`aae1460`](https://github.com/beatreichenbach/realflare/commit/aae1460ec9ff905a596cfc6f5a51339e344d803b))
* **viewer:** Update to latest qt_extension ([`6a7dc6c`](https://github.com/beatreichenbach/realflare/commit/6a7dc6c0b84ad3409d343d9162b62acbafc0ba4e))

## v0.4.3 (2023-05-21)
### Feature
* **window:** Add default widget states ([`f8ee4ee`](https://github.com/beatreichenbach/realflare/commit/f8ee4ee3b6f61dd5efd9c7b3249bb11bb6f92615))

### Fix
* **paramaters:** Use staticmethod to get lens model ([`4e13d4c`](https://github.com/beatreichenbach/realflare/commit/4e13d4c905e1fb6917c82ee250cd9d046d6e5a91))

## v0.4.2 (2023-05-20)
### Fix
* **sentry:** Only ask in gui ([`cc48d8e`](https://github.com/beatreichenbach/realflare/commit/cc48d8e725dd6cf609946333614d9ffc60a54764))

## v0.4.1 (2023-05-20)
### Fix
* **engine:** Remove old imports ([`5bd78f6`](https://github.com/beatreichenbach/realflare/commit/5bd78f6cfa9714466f5821613b35cceb880f923f))

## v0.4.0 (2023-05-20)
### Feature
* **storage:** Work on storage ([`537f4f8`](https://github.com/beatreichenbach/realflare/commit/537f4f84065dd5f7ef075cdca80022eac2560c74))
* **storage:** Move settings to storage ([`2901400`](https://github.com/beatreichenbach/realflare/commit/2901400f564d8258fd009e7d09033ba5fddaa81a))
* **sentry:** Add sentry check ([`d6c6f2b`](https://github.com/beatreichenbach/realflare/commit/d6c6f2b0c9f4facbd04be3b1f8f8fb25397b44be))

### Fix
* **storage:** Implement singleton ([`f5e27c9`](https://github.com/beatreichenbach/realflare/commit/f5e27c9cf8e66a44534be453535b6e489e347233))
* **benchmark:** Update and add log support ([`3069f5f`](https://github.com/beatreichenbach/realflare/commit/3069f5f34a44251aa7375eebd59d448960a7374c))
* **update:** Make dialog modal ([`b6cd472`](https://github.com/beatreichenbach/realflare/commit/b6cd4726475d8dce2e9a4c467bbf8e19757d1733))

### Documentation
* Changelog ([`cd6378f`](https://github.com/beatreichenbach/realflare/commit/cd6378f15f74b16aa2841c6a592694c103b9ea7b))

## v0.3.2 (2023-04-30)
### Fix
* Error handling(#59) ([`3f58677`](https://github.com/beatreichenbach/realflare/commit/3f586777016549e38859b73e006ea4fe872ad3ae))

### Documentation
* Update benchmark ([`bafe442`](https://github.com/beatreichenbach/realflare/commit/bafe442ce0736fb358dbac5cd0be0381dfde9bac))
* Update changelog ([`827fe32`](https://github.com/beatreichenbach/realflare/commit/827fe32713ad6ae3a70a0a7fc71fecd83c2b3bcc))

## v0.3.1 (2023-04-30)
### Fix
* **build:** Setup.bat typo ([`9600623`](https://github.com/beatreichenbach/realflare/commit/9600623ec9a1b99f883e1afee426f8275532cb88))

### Documentation
* Update changelog ([`c74e2b5`](https://github.com/beatreichenbach/realflare/commit/c74e2b5c5b899baf086d6bd48648c948fdb7a42c))

## v0.3.0 (2023-04-30)
### Feature
* Add image based light ([`421444f`](https://github.com/beatreichenbach/realflare/commit/421444fb7721f7ba32a1d6d099f938f49049080b))

### Documentation
* Update changelog ([`25e833f`](https://github.com/beatreichenbach/realflare/commit/25e833fff44adb8fa60b69ce8ddfa3117243fe6c))

## v0.2.0 (2023-04-29)
### Feature
* Add system parameters, allow selecting opencl device ([#51](https://github.com/beatreichenbach/realflare/issues/51)) ([`cf29045`](https://github.com/beatreichenbach/realflare/commit/cf29045f9068556e1d05efc733d6b0d84c050eea))

### Fix
* **build:** Allow spaces and better output for setup.bat ([`05ef41e`](https://github.com/beatreichenbach/realflare/commit/05ef41e8a0f23d61abe8cfbae2267ef4740c787b))

### Documentation
* Update readme, changelog and comments ([`fa781ea`](https://github.com/beatreichenbach/realflare/commit/fa781ea0299dbbdc6c4a14348af8cc852ec2a51a))

## v0.1.2 (2023-04-26)
### Fix
* **render:** Use path indexes for diagram ([`4c34414`](https://github.com/beatreichenbach/realflare/commit/4c344147f660be01f11eef99fb98d52709f0276f))
* **build:** Upgrade pip and fix venv install ([`da8fc72`](https://github.com/beatreichenbach/realflare/commit/da8fc7258b31ed937cded88ae0687b530aec4578))

### Documentation
* Add changelog ([`924ea7e`](https://github.com/beatreichenbach/realflare/commit/924ea7e7c0740706249382f1435b720f6c56a978))

## v0.1.1 (2023-04-25)
### Feature
* **benchmark:** Initial setup ([`33f40e2`](https://github.com/beatreichenbach/realflare/commit/33f40e29fa03e7460a860bde7cde86287b657378))

### Fix
* **benchmark:** Add current info ([`9c13d60`](https://github.com/beatreichenbach/realflare/commit/9c13d60a3b3dde785c44f9dfb1a40d63f8528d83))
* Rename package name ([`64d8e52`](https://github.com/beatreichenbach/realflare/commit/64d8e52dfb671f6e7b5286c323822d7309b0cb41))

### Documentation
* Update setup script location ([`c38fa36`](https://github.com/beatreichenbach/realflare/commit/c38fa36343f883114043e3fabd2191b24b4193bf))
