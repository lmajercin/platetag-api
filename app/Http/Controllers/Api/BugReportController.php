<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\BugReport;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class BugReportController extends Controller
{
    /**
     * List the authenticated user's own bug reports.
     * GET /api/v1/bug-reports
     */
    public function index(Request $request): JsonResponse
    {
        $reports = BugReport::where('user_id', $request->user()->id)
            ->orderByDesc('created_at')
            ->get(['id', 'title', 'status', 'admin_reply', 'created_at', 'resolved_at']);

        return response()->json($reports);
    }

    /**
     * Submit a bug report.
     * POST /api/v1/bug-reports
     */
    public function store(Request $request): JsonResponse
    {
        $data = $request->validate([
            'title'       => ['required', 'string', 'max:191'],
            'description' => ['required', 'string', 'max:5000'],
            'severity'    => ['nullable', 'in:low,medium,high,critical'],
            'category'    => ['nullable', 'in:ui,api,data,performance,other'],
            'app_version' => ['nullable', 'string', 'max:50'],
        ]);

        $bug = BugReport::create([
            'user_id'     => $request->user()?->id,
            'title'       => $data['title'],
            'description' => $data['description'],
            'severity'    => $data['severity'] ?? 'medium',
            'category'    => $data['category'] ?? 'other',
            'app_version' => $data['app_version'] ?? null,
            'status'      => 'open',
        ]);

        return response()->json([
            'id'      => $bug->id,
            'message' => 'Bug report submitted. Thank you.',
        ], 201);
    }

    /**
     * Delete the authenticated user's own bug report.
     * DELETE /api/v1/bug-reports/{id}
     */
    public function destroy(Request $request, int $id): JsonResponse
    {
        $report = BugReport::where('id', $id)
            ->where('user_id', $request->user()->id)
            ->first();

        if (!$report) {
            return response()->json(['message' => 'Not found'], 404);
        }

        $report->delete();

        return response()->json(['message' => 'Deleted']);
    }
}
