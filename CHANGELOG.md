#Change Log

## [Unreleased]

### Changed
 - `WebAPI` is no longer AsyncInit, and should not be awaited

### Added
 - Google flavor app/client JSON files can now be used to create `OAuth2`
 - Success local flow page styling, light/dark

### Removed
 - `EnumParam`, `EnumParams` types. Instead, use `set[str]` or `set[T]` where `T` is an enum type.