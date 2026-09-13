# DKC2 Android — adaptación inicial, 0.1.0-dev

**Estado: código de preparación experimental. No es un APK terminado ni una prueba de que el juego funciona en Android.**

Esta capa reutiliza el frontend Android existente de DKC1 y lo conecta a los encabezados y las unidades reales de DKC2. No modifica la rama de PC. La materialización se realiza en una carpeta nueva y se detiene si esta ya existe; no borra un checkout previo ni sus partidas.

## Base fijada

- DKC2: `YlPorts/DKC2Recomp` @ `e181419f2f8ff7b12494453e74840a4828bdb723`.
- Frontend Android: `YlPorts/DKC1Recomp-ANdroid` @ `e6cde9c43fc6a4d49c7eae5edba93b5bf2f5dea0`.
- Motor de DKC2: `mstan/snesrecomp` @ `fe6045c22bb023e15d825ec40bfc25387ec9253c`.
- SDL2, NDK y Gradle: pins del constructor Android reutilizado; NDK `28.2.13676358`, CMake `3.22.1`, SDK/Build Tools 35, Java 17.

El frontend fijado es la rama Android disponible en GitHub, no una afirmación de paridad con otros APK posteriores compartidos fuera de esa rama.

## Qué prepara

Paquete independiente `com.ylports.dkc2recomp.mobile`, Android 6+ y ARM64, selector SAF con ROM conservada en almacenamiento privado, menú de juego/configuración, controles multitáctiles editables, mandos, audio estéreo, pausa de ciclo de vida, registros y partidas separadas. Hereda el ajuste centrado de pantalla del frontend de DKC1.

El adaptador cambia la inicialización a `Dkc2GameInfo` y `Dkc2VideoSetWidescreen`, utiliza las unidades `runner/dkc2_*` y no usa las rutinas jugables de DKC1. Los helpers de audio/color copiados de DKC1 son utilidades del host; se mantienen sus avisos de licencia dentro de los assets del APK.

Se eliminan del menú Baby Kong, los controles de bordes específicos de DKC1 y la pestaña de créditos; las atribuciones y licencias permanecen en los archivos. El código Java reutilizado conserva algunos manejadores antiguos no expuestos y dos posiciones reservadas en el vector JNI para mantener el contrato del frontend.

## Límites, sin confundirlos con funciones verificadas

Solo se ofrecen 4:3 y el 16:9 experimental propio de DKC2. No se fuerza `g_ws_extra=96`: 21:9 y 16:10 no están habilitados. La cobertura panorámica de todos los niveles sigue sin certificarse.

La página Mods indica que la carga de mods todavía no está integrada. Música conserva el sonido original; MSU-1, shaders completos y rebobinado no se anuncian como implementados. No es una copia idéntica de todas las opciones de PC ni del APK DKC1 v1 compartido fuera del pin indicado.

El constructor necesita la ROM privada para generar y enlazar las unidades nativas AOT. El framework conserva su intérprete de respaldo y su modelo de hardware SNES, como el proyecto de PC; no se afirma que sea un motor sin ninguna emulación de hardware.

## ROM necesaria

DKC2 **North America / USA v1.0**, cuerpo de 4.194.304 bytes:

```text
CRC32: 006364DB
SHA-256: 35421a9af9dd011b40b91f792192af9f99c93201d8d394026bdfb42cbf2d8633
```

Se admite `.sfc` o `.smc`, con o sin cabecera de copiador de 512 bytes. El script verifica los bytes, no el nombre del archivo. No descarga ROMs, no admite enlaces remotos como entrada de ROM y no publica la ROM ni las fuentes generadas. Una ROM de DKC1, DKC2 PAL o revisión 1 no sustituye esa entrada.

## Preparar solo código

Desde el repositorio que contiene `android_port/`:

```sh
python android_port/bootstrap.py --output ../DKC2Recomp-Android-work --dependencies
```

Necesita Git, Python y conexión para obtener las dependencias públicas. Este comando **no produce un APK jugable**.

## Generar y compilar con tu ROM local

Para una carpeta nueva:

```sh
python android_port/bootstrap.py --output ../DKC2Recomp-Android-work --rom "/ruta/privada/DKC2.sfc" --build --sdk "/ruta/Android/Sdk"
```

Si ya preparaste la carpeta, no repitas bootstrap sobre ella. Ejecuta el constructor dentro de esa copia:

```sh
cd ../DKC2Recomp-Android-work
python android/tools/build_android.py --rom "/ruta/privada/DKC2.sfc" --sdk "/ruta/Android/Sdk"
```

El resultado esperado, únicamente tras una compilación exitosa, es `android/app/build/outputs/apk/debug/app-debug.apk`. Firma de desarrollo: conserva la misma keystore para que futuras compilaciones puedan actualizar esa instalación. La app DKC2 no reemplaza DKC1.

## Pruebas y aceptación

```sh
python -m unittest discover -s android_port/tests -v
```

Estas pruebas son sintéticas: comprueban hashes, validación de entrada, límites de edición y configuración. No son una prueba del juego ni de instalación. `DKC2_ANDROID_SOURCE_CHECK=ON` genera solo objetos C del host para comprobar interfaces NDK; no crea `libmain.so`, juego ficticio ni APK.

Pendiente antes de llamar a esto un port jugable: generación con la ROM exacta, enlace final de todas las unidades, verificación del APK, arranque/título/partida con sonido, cierre/reapertura y persistencia, controles simultáneos, pausa/reanudación y aceptación de 16:9 en un dispositivo real.
