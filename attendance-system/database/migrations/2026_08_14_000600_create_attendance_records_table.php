<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * Attendance records — local copy of synchronized punch transactions.
 *
 * Source: Python Integration Service → Phase 3 REST API → here.
 * The Laravel app never reads directly from the SpeedFace device.
 *
 * Duplicate protection:
 *   UNIQUE(device_id, device_user_id, punch_datetime, punch_state, verification_type)
 *   This mirrors the Python service's own dedup strategy exactly.
 *
 * Source traceability:
 *   Every record retains device_id, device_user_id, source_record_id,
 *   and raw_data so it can always be traced back to the SpeedFace source.
 *
 * No business calculations (late, overtime, absent) are stored here.
 * Those belong to Phase 6.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::create('attendance_records', function (Blueprint $table) {
            $table->id();

            // Source device
            $table->foreignId('device_id')->constrained()->cascadeOnDelete();

            // Device-side identifiers (no assumptions about employee mapping)
            $table->string('device_user_id', 50)->index();

            // Resolved employee (null if not yet mapped)
            $table->foreignId('employee_id')->nullable()->constrained()->nullOnDelete();

            // Punch data (normalized from Phase 3 API)
            $table->dateTime('punch_datetime')->index();
            $table->unsignedTinyInteger('punch_state')->default(0);   // 0=check_in, 1=check_out …
            $table->string('punch_state_label', 30)->nullable();       // 'Check In', 'Check Out' …
            $table->unsignedTinyInteger('verification_type')->default(0); // 10=face, 0=fingerprint …
            $table->string('verification_type_label', 30)->nullable();  // 'Face', 'Fingerprint' …

            // Source traceability
            $table->unsignedInteger('source_record_id')->nullable(); // Python DB id, if available
            $table->text('raw_data')->nullable();                     // original JSON from API

            $table->timestamp('synced_at')->useCurrent();

            // Duplicate prevention: mirrors Phase 3 Python unique constraint exactly
            $table->unique(
                ['device_id', 'device_user_id', 'punch_datetime', 'punch_state', 'verification_type'],
                'unique_attendance_punch'
            );

            // Performance indexes for the most common filter patterns
            $table->index(['device_id', 'punch_datetime']);
            $table->index(['employee_id', 'punch_datetime']);
            $table->index(['device_id', 'device_user_id', 'punch_datetime']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('attendance_records');
    }
};
