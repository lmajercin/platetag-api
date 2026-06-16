<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Symfony\Component\HttpFoundation\StreamedResponse;

class SessionController extends Controller
{
    /**
     * GET /api/v1/auth/sessions
     * List all sessions for the current user, with plate + region counts.
     */
    public function index(Request $request): JsonResponse
    {
        $user = $request->user();

        $sessions = DB::table('discovery_sessions as ds')
            ->where('ds.user_id', $user->id)
            ->leftJoin('user_discovered_plates as udp', 'udp.session_id', '=', 'ds.id')
            ->leftJoin('plates', 'plates.id', '=', 'udp.plate_id')
            ->leftJoin('series', 'series.id', '=', 'plates.series_id')
            ->leftJoin('regions', 'regions.id', '=', 'series.region_id')
            ->select(
                'ds.id',
                'ds.name',
                'ds.is_default',
                'ds.created_at',
                DB::raw('COUNT(DISTINCT udp.plate_id) as plate_count'),
                DB::raw('COUNT(DISTINCT regions.id)   as region_count'),
                DB::raw('MIN(udp.discovered_at)       as first_discovery'),
                DB::raw('MAX(udp.discovered_at)       as latest_discovery')
            )
            ->groupBy('ds.id', 'ds.name', 'ds.is_default', 'ds.created_at')
            ->orderBy('ds.created_at')
            ->get()
            ->map(fn($r) => [
                'id'               => $r->id,
                'name'             => $r->name,
                'is_default'       => (bool) $r->is_default,
                'created_at'       => $r->created_at,
                'plate_count'      => (int) $r->plate_count,
                'region_count'     => (int) $r->region_count,
                'first_discovery'  => $r->first_discovery,
                'latest_discovery' => $r->latest_discovery,
            ]);

        return response()->json(['data' => $sessions]);
    }

    /**
     * POST /api/v1/auth/sessions
     * Create a new session. Immediately becomes the "active" session on the client.
     */
    public function store(Request $request): JsonResponse
    {
        $user = $request->user();

        $data = $request->validate([
            'name' => ['required', 'string', 'max:100'],
        ]);

        $id = DB::table('discovery_sessions')->insertGetId([
            'user_id'    => $user->id,
            'name'       => $data['name'],
            'is_default' => false,
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return response()->json([
            'id'         => $id,
            'name'       => $data['name'],
            'is_default' => false,
            'created_at' => now()->toISOString(),
        ], 201);
    }

    /**
     * PATCH /api/v1/auth/sessions/{id}
     * Rename a session. Cannot rename the default General session via name field
     * (is_default is not editable), but name CAN be changed even on the default session.
     */
    public function update(Request $request, int $id): JsonResponse
    {
        $user = $request->user();

        $session = DB::table('discovery_sessions')
            ->where('id', $id)
            ->where('user_id', $user->id)
            ->first();

        if (!$session) {
            return response()->json(['message' => 'Session not found.'], 404);
        }

        $data = $request->validate([
            'name' => ['required', 'string', 'max:100'],
        ]);

        DB::table('discovery_sessions')
            ->where('id', $id)
            ->where('user_id', $user->id)
            ->update(['name' => $data['name'], 'updated_at' => now()]);

        return response()->json(['id' => $id, 'name' => $data['name']]);
    }

    /**
     * DELETE /api/v1/auth/sessions/{id}
     * Delete a session. Plates are NOT deleted — their session_id is set to NULL
     * by the ON DELETE SET NULL FK constraint. Cannot delete the default session.
     */
    public function destroy(Request $request, int $id): JsonResponse
    {
        $user = $request->user();

        $session = DB::table('discovery_sessions')
            ->where('id', $id)
            ->where('user_id', $user->id)
            ->first();

        if (!$session) {
            return response()->json(['message' => 'Session not found.'], 404);
        }

        if ($session->is_default) {
            return response()->json(['message' => 'The General session cannot be deleted.'], 422);
        }

        DB::table('discovery_sessions')
            ->where('id', $id)
            ->where('user_id', $user->id)
            ->delete();

        return response()->json(['deleted' => true]);
    }

    /**
     * GET /api/v1/auth/sessions/{id}/export
     * Stream a CSV of all discoveries in a given session.
     */
    public function export(Request $request, int $id): StreamedResponse|JsonResponse
    {
        $user = $request->user();

        $session = DB::table('discovery_sessions')
            ->where('id', $id)
            ->where('user_id', $user->id)
            ->first();

        if (!$session) {
            return response()->json(['message' => 'Session not found.'], 404);
        }

        $rows = DB::table('user_discovered_plates as udp')
            ->join('plates', 'plates.id', '=', 'udp.plate_id')
            ->join('series', 'series.id', '=', 'plates.series_id')
            ->leftJoin('regions', 'regions.id', '=', 'series.region_id')
            ->leftJoin('categories', 'categories.id', '=', 'plates.category_id')
            ->where('udp.user_id', $user->id)
            ->where('udp.session_id', $id)
            ->select([
                'plates.name as plate_name',
                'series.name as series_name',
                'series.country_code',
                'regions.name as region_name',
                'categories.name as category_name',
                'udp.discovered_at',
                'udp.notes',
                'udp.latitude',
                'udp.longitude',
                'udp.location_label',
            ])
            ->orderBy('udp.discovered_at')
            ->get();

        $filename = preg_replace('/[^a-z0-9_-]/i', '_', $session->name) . '_export.csv';

        return response()->streamDownload(function () use ($rows) {
            $out = fopen('php://output', 'w');
            fputcsv($out, ['Plate', 'Series', 'Country', 'Region', 'Category',
                           'Discovered At', 'Notes', 'Latitude', 'Longitude', 'Location Label']);
            foreach ($rows as $row) {
                fputcsv($out, [
                    $row->plate_name,
                    $row->series_name,
                    $row->country_code,
                    $row->region_name  ?? '',
                    $row->category_name ?? '',
                    $row->discovered_at,
                    $this->sanitizeCsv($row->notes        ?? ''),
                    $row->latitude     ?? '',
                    $row->longitude    ?? '',
                    $this->sanitizeCsv($row->location_label ?? ''),
                ]);
            }
            fclose($out);
        }, $filename, ['Content-Type' => 'text/csv']);
    }

    /**
     * Strip leading spreadsheet formula characters from user-supplied strings
     * to prevent CSV formula injection attacks.
     */
    private function sanitizeCsv(?string $value): string
    {
        if ($value === null || $value === '') {
            return '';
        }
        if (in_array(mb_substr($value, 0, 1), ['=', '+', '-', '@'], true)) {
            return "\t" . $value;
        }
        return $value;
    }
}
