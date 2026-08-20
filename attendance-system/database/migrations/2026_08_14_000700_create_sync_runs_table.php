<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * Sync runs — audit trail of every synchronisation attempt.
 *
 * Records are created when Laravel triggers a sync via POST /api/sync
 * and updated when the result is retrieved from GET /api/sync/status.
 *
 * status: pending | running | success | partial | failed
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::create('sync_runs', function (Blueprint $table) {
            $table->id();
            $table->foreignId('device_id')->nullable()->constrained()->nullOnDelete();
            $table->foreignId('triggered_by')->nullable()->constrained('users')->nullOnDelete();
            $table->string('status', 20)->default('pending')->index();
            $table->timestamp('started_at')->nullable();
            $table->timestamp('completed_at')->nullable();
            $table->unsignedInteger('records_read')->default(0);
            $table->unsignedInteger('records_inserted')->default(0);
            $table->unsignedInteger('records_skipped')->default(0);
            $table->unsignedInteger('records_failed')->default(0);
            $table->unsignedInteger('records_rejected')->default(0); // failed Laravel-side validation
            $table->decimal('duration_seconds', 8, 2)->nullable();
            $table->text('error_message')->nullable();
            $table->string('source', 20)->default('manual'); // manual | scheduled | api
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('sync_runs');
    }
};
