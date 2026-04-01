<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\BugReport;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class BugReportController extends Controller
{
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
}
