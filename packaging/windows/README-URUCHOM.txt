MIANEM — WINDOWS PORTABLE

Uruchomienie
============

1. Rozpakuj pobrany ZIP do zwykłego folderu, np. Pobrane\Mianem.
2. Kliknij dwukrotnie Mianem.exe.
3. Pojawi się małe okno Mianem, a aplikacja sama otworzy się w domyślnej przeglądarce.
4. Po zakończeniu kliknij „Zakończ” w małym oknie Mianem.

Nie trzeba instalować Pythona, FastAPI ani żadnych dodatkowych bibliotek.
Nie są wymagane uprawnienia administratora.

Wymagania
=========

- Windows 10 lub Windows 11, 64-bit.
- Połączenie z internetem do GBIF, sprawdzania live .com przez Verisign RDAP oraz screeningu marki.

Dane lokalne
============

Historia, zapisane decyzje i własne obszary pozostają lokalnie na komputerze użytkownika w:

%LOCALAPPDATA%\PMindLab\Mianem

Pakiet nie zawiera prywatnej bazy danych autora ani żadnych sekretów/API keys.

Odzyskiwanie zapisów ze starszej wersji
========================================

Jeżeli nowa baza portable jest pusta, Mianem nie ukrywa tego faktu.

- Gdy obok uruchamianej aplikacji znajduje dokładnie jeden oczywisty starszy plik `data\namelab.db` z zapisanymi kandydatami, importuje go do lokalnego magazynu portable.
- Gdy nie da się jednoznacznie znaleźć starej bazy, aplikacja zapyta, czy chcesz wskazać poprzedni plik `namelab.db` ręcznie.
- Niepusta aktualna baza portable nigdy nie jest automatycznie nadpisywana.
- Istniejący pusty plik docelowy jest zachowywany jako `namelab.before-import*.db` przed importem.

Opcjonalne API keys
===================

Aplikacja działa bez kluczy. Jeżeli potrzebujesz szerszego screeningu marki, możesz utworzyć obok Mianem.exe plik .env, np.:

GITHUB_TOKEN=...
BRAVE_SEARCH_API_KEY=...

Nie udostępniaj pliku .env innym osobom.

Windows SmartScreen
===================

Ten build nie jest podpisany komercyjnym certyfikatem Windows. Przy pierwszym uruchomieniu Windows może pokazać ostrzeżenie SmartScreen. Dla pliku otrzymanego bezpośrednio z kanonicznego repo PMindLab można użyć „Więcej informacji” → „Uruchom mimo to”.

Diagnostyka
===========

Jeśli Mianem nie uruchomi się poprawnie, komunikat pokaże rzeczywisty typ błędu. Szczegóły są też zapisywane lokalnie w:

%LOCALAPPDATA%\PMindLab\Mianem\startup-error.txt

Bezpieczeństwo
==============

Mianem nasłuchuje wyłącznie lokalnie pod adresem 127.0.0.1. Nie wystawia serwera do sieci LAN ani Internetu.
