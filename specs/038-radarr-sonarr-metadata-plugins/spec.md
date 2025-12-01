# Feature Specification: Radarr and Sonarr Metadata Plugins

**Feature Branch**: `038-radarr-sonarr-metadata-plugins`
**Created**: 2025-12-01
**Status**: Draft
**Input**: User description: "As a user I'd like to take advantage of existing online services to help me populate metadata for my existing video library in order to make the library more accessible for finding relevant content. Create plugins to access metadata through the Radarr and Sonarr APIs. Specifically including the original language of the release to allow properly tagging the video tracks in a file."

## Clarifications

### Session 2025-12-01

- Q: How should path matching work between VPO and Radarr/Sonarr? → A: Require identical paths - no path mapping support
- Q: How should API keys be stored securely? → A: Store in VPO config file with filesystem permissions
- Q: How long should cached API responses remain valid? → A: Session cache only - cleared after scan operation completes

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Configure Radarr Connection (Priority: P1)

A user with an existing Radarr installation wants to connect VPO to their Radarr instance to fetch movie metadata. They provide their Radarr server URL and API key, and VPO validates the connection before storing the configuration.

**Why this priority**: Without successful connection and configuration, no metadata enrichment is possible. This is the foundational capability that enables all other features.

**Independent Test**: Can be fully tested by configuring a Radarr connection and receiving confirmation of successful authentication, delivering immediate value that the system can communicate with Radarr.

**Acceptance Scenarios**:

1. **Given** a valid Radarr URL and API key, **When** the user configures the Radarr plugin, **Then** the system validates the connection and confirms successful authentication.
2. **Given** an invalid API key, **When** the user attempts to configure the Radarr plugin, **Then** the system displays a clear error message indicating authentication failed.
3. **Given** an unreachable Radarr URL, **When** the user attempts to configure the connection, **Then** the system reports a connection error with timeout details.

---

### User Story 2 - Configure Sonarr Connection (Priority: P1)

A user with an existing Sonarr installation wants to connect VPO to their Sonarr instance to fetch TV series metadata. They provide their Sonarr server URL and API key, and VPO validates the connection before storing the configuration.

**Why this priority**: Similar to Radarr, Sonarr connection is foundational for TV series metadata enrichment. Both movie and TV metadata plugins are equally important for users with mixed libraries.

**Independent Test**: Can be fully tested by configuring a Sonarr connection and receiving confirmation of successful authentication.

**Acceptance Scenarios**:

1. **Given** a valid Sonarr URL and API key, **When** the user configures the Sonarr plugin, **Then** the system validates the connection and confirms successful authentication.
2. **Given** an invalid API key, **When** the user attempts to configure the Sonarr plugin, **Then** the system displays a clear error message indicating authentication failed.
3. **Given** an unreachable Sonarr URL, **When** the user attempts to configure the connection, **Then** the system reports a connection error with timeout details.

---

### User Story 3 - Enrich Movie Metadata from Radarr (Priority: P2)

A user scans a movie file in their library. The Radarr plugin matches the file to a movie in the user's Radarr library and enriches VPO's metadata with information from Radarr, including the movie's original language, title, year, and other available metadata.

**Why this priority**: This is the core value proposition for movie files - enriching scanned files with authoritative metadata from Radarr.

**Independent Test**: Can be tested by scanning a movie file that exists in Radarr and verifying that metadata fields (especially original language) are populated in VPO.

**Acceptance Scenarios**:

1. **Given** a movie file path that matches a movie in the user's Radarr library, **When** the file is scanned, **Then** the plugin enriches the file metadata with original language, title, and year from Radarr.
2. **Given** a movie file that does not match any movie in Radarr, **When** the file is scanned, **Then** the plugin logs that no match was found and leaves metadata unchanged.
3. **Given** multiple potential matches in Radarr (e.g., remakes with same title), **When** the file is scanned, **Then** the plugin logs a warning about multiple matches and uses the first match by Radarr ID (deterministic ordering).

---

### User Story 4 - Enrich TV Series Metadata from Sonarr (Priority: P2)

A user scans a TV episode file in their library. The Sonarr plugin matches the file to a series in the user's Sonarr library and enriches VPO's metadata with information from Sonarr, including the series' original language, title, season/episode information, and other available metadata.

**Why this priority**: This is the core value proposition for TV files - enriching scanned files with authoritative metadata from Sonarr.

**Independent Test**: Can be tested by scanning a TV episode file that exists in Sonarr and verifying that metadata fields (especially original language) are populated in VPO.

**Acceptance Scenarios**:

1. **Given** a TV episode file path that matches a series in the user's Sonarr library, **When** the file is scanned, **Then** the plugin enriches the file metadata with original language, series title, and season/episode numbers from Sonarr.
2. **Given** a TV file that does not match any series in Sonarr, **When** the file is scanned, **Then** the plugin logs that no match was found and leaves metadata unchanged.
3. **Given** a file path that matches a series but not a specific episode (e.g., bonus content), **When** the file is scanned, **Then** the plugin enriches with series-level metadata only.

---

### User Story 5 - Apply Original Language to Video Tracks (Priority: P3)

A user has a movie or TV file enriched with original language metadata from Radarr or Sonarr. They want to use this information in a VPO policy to automatically tag video tracks with the correct language when the video track has no language tag or an incorrect tag.

**Why this priority**: This is the key use case explicitly requested by the user - using original language to properly tag video tracks. Depends on successful metadata enrichment.

**Independent Test**: Can be tested by creating a policy that uses original language metadata to set video track language, applying it to a file with enriched metadata, and verifying the video track is tagged correctly.

**Acceptance Scenarios**:

1. **Given** a file with enriched original language metadata and a video track with no language tag, **When** a policy using original_language condition is applied, **Then** the video track is tagged with the original language.
2. **Given** a file with enriched original language metadata and a video track with a language tag matching the original language, **When** a policy is applied, **Then** no changes are made to the track.
3. **Given** a file without original language metadata (no Radarr/Sonarr match), **When** a policy using original_language condition is applied, **Then** the policy gracefully skips the condition with appropriate logging.

---

### User Story 6 - View Enriched Metadata in UI (Priority: P3)

A user wants to see metadata enriched from Radarr or Sonarr when viewing file details in the VPO web UI. The UI displays the source of the metadata (Radarr/Sonarr) and key enriched fields including original language.

**Why this priority**: Provides visibility into what metadata was enriched and from where, helping users verify the matching worked correctly.

**Independent Test**: Can be tested by viewing a file in the web UI that has been enriched and verifying the metadata source and enriched fields are displayed.

**Acceptance Scenarios**:

1. **Given** a file enriched with Radarr metadata, **When** viewing the file details in the web UI, **Then** the UI shows "Source: Radarr" and displays enriched fields including original language.
2. **Given** a file enriched with Sonarr metadata, **When** viewing the file details in the web UI, **Then** the UI shows "Source: Sonarr" and displays enriched fields including original language, series name, and season/episode.
3. **Given** a file with no external metadata enrichment, **When** viewing the file details, **Then** no external source is displayed and only intrinsic metadata is shown.

---

### Edge Cases

- What happens when Radarr/Sonarr is temporarily unavailable during a scan? The system retries with exponential backoff, then proceeds without enrichment, logging the failure.
- How does the system handle files not managed by Radarr/Sonarr? Files are matched by path; unmatched files proceed without enrichment.
- What happens when API rate limits are exceeded? The system detects rate limit responses and implements appropriate delays before retrying.
- How are multiple files for the same movie/series handled? Each file is matched independently; the plugin caches API responses to minimize repeated lookups.
- What happens when Radarr/Sonarr metadata changes after initial enrichment? Re-scanning the file refreshes enriched metadata from the external source.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a Radarr plugin that connects to Radarr v3 API
- **FR-002**: System MUST provide a Sonarr plugin that connects to Sonarr v3 API
- **FR-003**: Both plugins MUST validate API credentials on configuration
- **FR-004**: Plugins MUST subscribe to the `file.scanned` event to enrich metadata
- **FR-005**: Plugins MUST match scanned files to items in the user's Radarr/Sonarr library by file path
- **FR-006**: Plugins MUST retrieve and store the original language of matched items
- **FR-007**: Plugins MUST retrieve and store title, year (movies) or series name, season/episode (TV)
- **FR-008**: Plugins MUST handle API errors gracefully without blocking scan operations
- **FR-009**: System MUST cache API responses for the duration of a scan operation (session cache) to minimize redundant network requests; cache is cleared after scan completes
- **FR-010**: System MUST expose enriched metadata for use in policy conditions
- **FR-011**: System MUST display enriched metadata and source in the web UI file details view
- **FR-012**: Plugins MUST log match successes, failures, and API errors at appropriate levels
- **FR-013**: Configuration MUST support separate instances for Radarr and Sonarr (URL + API key each), stored in VPO's config file with filesystem permissions for security
- **FR-014**: System MUST normalize language codes from Radarr/Sonarr to VPO's standard format (ISO 639-2/B)

### Key Entities

- **Plugin Configuration**: Stores connection details (URL, API key) for each external service
- **Metadata Enrichment**: Additional metadata fields retrieved from external sources (original_language, external_title, external_year, external_source, series_name, season_number, episode_number)
- **Match Result**: Represents the outcome of attempting to match a file to an external service (matched, unmatched, uncertain, error)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can successfully configure Radarr/Sonarr connections with valid credentials within 30 seconds
- **SC-002**: Files matching items in Radarr/Sonarr libraries are enriched with original language on first scan
- **SC-003**: 95% of files managed by Radarr/Sonarr are correctly matched during scanning
- **SC-004**: Metadata enrichment completes within 1 second per file when external service is available
- **SC-005**: Users can view enriched metadata including original language in the web UI
- **SC-006**: Policies can successfully use original_language from enriched metadata to tag video tracks
- **SC-007**: API failures do not block or significantly slow scan operations (graceful degradation)

## Assumptions

- Users have existing, functional Radarr and/or Sonarr installations they want to integrate
- Radarr and Sonarr instances are accessible over the network from where VPO runs
- Files in VPO must be stored at identical paths as seen by Radarr/Sonarr (no path mapping support; both systems must access the same filesystem paths)
- Users have valid API keys with read access to their Radarr/Sonarr instances
- The Radarr v3 and Sonarr v3 APIs remain stable and backward-compatible
- Original language information is available in Radarr/Sonarr for the majority of items (populated from TMDb/TVDb)
